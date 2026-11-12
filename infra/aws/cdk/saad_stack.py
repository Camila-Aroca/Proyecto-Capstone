"""Pila CDK del despliegue to-be del SAAD en AWS (us-east-1).

Recursos:
- VPC propia con dos subredes públicas y sin NAT Gateway: la tarea de la API usa una IP
  pública para bajar su imagen de ECR y sus datos de S3 (un NAT costaría más que la tarea).
- Bucket de datos privado: `data/processed/`, `reports/` y `data/raw/poblacion/`, que el
  equipo sube con `infra/aws/scripts/subir_datos.sh`. La API solo puede leerlo.
- Servicio ECS Fargate `saad-api` (0,5 vCPU, 2 GB) detrás de un ALB público. El ALB solo
  acepta tráfico desde CloudFront: el grupo de seguridad admite la prefix list gestionada
  de CloudFront y el listener exige un encabezado secreto; lo demás recibe 403.
- Bucket del sitio privado, leído solo por CloudFront mediante Origin Access Control.
- Distribución CloudFront con la URL `*.cloudfront.net` (sin dominio propio):
  `/api/*` va al ALB sin caché y el resto al sitio estático.
- Alarmas de CloudWatch (API sin tareas sanas, errores 5xx, CPU y memoria de la tarea,
  errores en los logs de la API y errores de CloudFront) que avisan a un tema SNS.

El pipeline no corre en AWS: se ejecuta en el equipo y sus outputs se suben a S3.

Contexto (`-c clave=valor` o `cdk.json`):
- `api_tag` (obligatorio): etiqueta de la imagen `saad-api` en ECR (SHA corto del commit).
- `cloudfront_prefix_list` (obligatorio): id de `com.amazonaws.global.cloudfront.origin-facing`.
- `origin_secret` (obligatorio): valor del encabezado secreto CloudFront → ALB.
- `api_desired_count` (opcional, 1): 0 deja el servicio creado pero apagado.
- `api_cpu` y `api_memory` (opcionales, 512 y 2048): tamaño de la tarea en unidades de CPU y MiB.
  Subirlos temporalmente (p. ej. 4096 y 8192) acelera el cálculo del pronóstico en memoria
  cuando el persistido no está vigente.
- `api_pronostico_desactualizado` (opcional, 0): con 1, la API sirve el pronóstico guardado
  aunque no esté vigente, con una advertencia visible, en vez de recalcularlo.
- `ecr_repo` (opcional, `saad-api`): repositorio ECR, creado por `publicar_imagen.sh`.
- `alarm_email` (opcional): correo suscrito al tema SNS de las alarmas. AWS envía un correo
  de confirmación que hay que aceptar; sin este valor las alarmas solo quedan en la consola.
"""

from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
)
from constructs import Construct

RAIZ_REPO = Path(__file__).resolve().parents[3]
FRONTEND_DIST = RAIZ_REPO / "frontend" / "dist"
ENCABEZADO_ORIGEN = "X-Origin-Verify"
PUERTO_API = 8000
RUTA_SALUD = "/api/v1/salud"


def _contexto(scope: Construct, clave: str, defecto: str | None = None) -> str:
    valor = scope.node.try_get_context(clave)
    if valor in (None, ""):
        if defecto is None:
            raise ValueError(f"Falta el contexto CDK '{clave}' (usar -c {clave}=...).")
        return defecto
    return str(valor)


class SaadStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        api_tag = _contexto(self, "api_tag")
        prefix_list = _contexto(self, "cloudfront_prefix_list")
        origin_secret = _contexto(self, "origin_secret")
        desired_count = int(_contexto(self, "api_desired_count", "1"))
        api_cpu = int(_contexto(self, "api_cpu", "512"))
        api_memory = int(_contexto(self, "api_memory", "2048"))
        pronostico_desactualizado = _contexto(self, "api_pronostico_desactualizado", "0")
        repo_nombre = _contexto(self, "ecr_repo", "saad-api")
        correo_alarmas = self.node.try_get_context("alarm_email") or ""

        # --- Red ---------------------------------------------------------------
        vpc = ec2.Vpc(
            self, "Vpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="publica", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
            ],
        )

        # --- Almacenamiento ----------------------------------------------------
        # Datos y sitio se pueden borrar con la pila: los datos se vuelven a subir desde el
        # equipo y el sitio se reconstruye desde el repositorio.
        datos = s3.Bucket(
            self, "Datos",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        sitio = s3.Bucket(
            self, "Sitio",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # --- API en ECS Fargate ------------------------------------------------
        cluster = ecs.Cluster(self, "ClusterEcs", vpc=vpc, cluster_name="saad")
        repo = ecr.Repository.from_repository_name(self, "RepoApi", repo_nombre)

        tarea = ecs.FargateTaskDefinition(
            self, "TareaApi",
            cpu=api_cpu,
            memory_limit_mib=api_memory,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )
        datos.grant_read(tarea.task_role)
        tarea.add_container(
            "api",
            image=ecs.ContainerImage.from_ecr_repository(repo, api_tag),
            port_mappings=[ecs.PortMapping(container_port=PUERTO_API)],
            environment={
                "SAAD_S3_BUCKET": datos.bucket_name,
                "SAAD_S3_PREFIX": "",
                "SAAD_USAR_PRONOSTICO_DESACTUALIZADO": pronostico_desactualizado,
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="api",
                log_group=(logs_api := logs.LogGroup(
                    self, "LogsApi",
                    log_group_name="/ecs/saad-api",
                    retention=logs.RetentionDays.TWO_WEEKS,
                    removal_policy=RemovalPolicy.DESTROY,
                )),
            ),
        )

        sg_alb = ec2.SecurityGroup(self, "SgAlb", vpc=vpc, description="ALB SAAD: solo CloudFront")
        sg_alb.add_ingress_rule(ec2.Peer.prefix_list(prefix_list), ec2.Port.tcp(80), "CloudFront")
        sg_api = ec2.SecurityGroup(self, "SgApi", vpc=vpc, description="API SAAD: solo desde el ALB")
        sg_api.add_ingress_rule(sg_alb, ec2.Port.tcp(PUERTO_API), "ALB")

        servicio = ecs.FargateService(
            self, "ServicioApi",
            cluster=cluster,
            service_name="saad-api",
            task_definition=tarea,
            desired_count=desired_count,
            assign_public_ip=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[sg_api],
            # La API carga sus datos al arrancar: ECS no la evalúa durante ese tiempo.
            health_check_grace_period=Duration.seconds(300),
            min_healthy_percent=100,
            max_healthy_percent=200,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        )

        alb = elbv2.ApplicationLoadBalancer(
            self, "Alb", vpc=vpc, internet_facing=True, security_group=sg_alb,
        )
        listener = alb.add_listener(
            "Http", port=80, open=False,
            default_action=elbv2.ListenerAction.fixed_response(403, message_body="Acceso solo vía CloudFront"),
        )
        grupo_api = listener.add_targets(
            "Api",
            port=PUERTO_API,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[servicio],
            priority=1,
            conditions=[elbv2.ListenerCondition.http_header(ENCABEZADO_ORIGEN, [origin_secret])],
            health_check=elbv2.HealthCheck(path=RUTA_SALUD, healthy_http_codes="200", interval=Duration.seconds(30)),
            deregistration_delay=Duration.seconds(30),
        )

        # --- CloudFront --------------------------------------------------------
        origen_api = origins.HttpOrigin(
            alb.load_balancer_dns_name,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
            custom_headers={ENCABEZADO_ORIGEN: origin_secret},
            read_timeout=Duration.seconds(60),
        )
        distribucion = cloudfront.Distribution(
            self, "Distribucion",
            comment="SAAD: sitio y API",
            default_root_object="index.html",
            price_class=cloudfront.PriceClass.PRICE_CLASS_ALL,
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(sitio),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origen_api,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),
            },
        )

        # El build del frontend se publica con la pila si existe (`npm run build`).
        if FRONTEND_DIST.is_dir():
            s3deploy.BucketDeployment(
                self, "PublicarSitio",
                sources=[s3deploy.Source.asset(str(FRONTEND_DIST))],
                destination_bucket=sitio,
                distribution=distribucion,
                distribution_paths=["/index.html"],
                prune=True,
            )

        self._alarmas(
            correo=str(correo_alarmas),
            api_encendida=desired_count > 0,
            servicio=servicio,
            grupo_api=grupo_api,
            alb=alb,
            logs_api=logs_api,
            distribucion=distribucion,
        )

        CfnOutput(self, "Url", value=f"https://{distribucion.distribution_domain_name}")
        CfnOutput(self, "BucketDatos", value=datos.bucket_name)
        CfnOutput(self, "BucketSitio", value=sitio.bucket_name)
        CfnOutput(self, "DistribucionId", value=distribucion.distribution_id)
        CfnOutput(self, "Cluster", value=cluster.cluster_name)
        CfnOutput(self, "Servicio", value=servicio.service_name)

    def _alarmas(
        self,
        *,
        correo: str,
        api_encendida: bool,
        servicio: ecs.FargateService,
        grupo_api: elbv2.ApplicationTargetGroup,
        alb: elbv2.ApplicationLoadBalancer,
        logs_api: logs.LogGroup,
        distribucion: cloudfront.Distribution,
    ) -> None:
        """Alarmas de operación de la API y del sitio; todas avisan al mismo tema SNS.

        Umbrales pensados para una sola tarea con tráfico académico bajo. Los datos
        faltantes cuentan como "sin problema", salvo las tareas sanas, que es justamente lo
        que se quiere detectar cuando la API cae.
        """
        tema = sns.Topic(self, "AlarmasTema", display_name="Alarmas SAAD")
        if correo:
            tema.add_subscription(subs.EmailSubscription(correo))
        accion = cw_actions.SnsAction(tema)
        cinco_min = Duration.minutes(5)
        sin_datos_ok = cloudwatch.TreatMissingData.NOT_BREACHING

        def alarma(id_: str, descripcion: str, metrica: cloudwatch.IMetric, umbral: float,
                   periodos: int, comparacion: cloudwatch.ComparisonOperator,
                   sin_datos: cloudwatch.TreatMissingData = sin_datos_ok) -> None:
            nueva = cloudwatch.Alarm(
                self, id_,
                alarm_name=f"saad-{id_}",
                alarm_description=descripcion,
                metric=metrica,
                threshold=umbral,
                evaluation_periods=periodos,
                comparison_operator=comparacion,
                treat_missing_data=sin_datos,
            )
            nueva.add_alarm_action(accion)
            nueva.add_ok_action(accion)

        mayor = cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
        menor = cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD

        # Con el servicio apagado a propósito (api_desired_count=0) esta alarma sonaría siempre.
        if api_encendida:
            alarma(
                "api-sin-tareas-sanas",
                "La API no tiene ninguna tarea sana detrás del ALB: el sitio queda sin datos.",
                grupo_api.metrics.healthy_host_count(period=Duration.minutes(1), statistic="Minimum"),
                1, 3, menor, cloudwatch.TreatMissingData.BREACHING,
            )
        alarma(
            "api-errores-5xx",
            "La API respondió 10 o más errores 5xx en 5 minutos. Los 503 breves al arrancar son "
            "esperables; si persiste, revisar /api/v1/salud y los logs.",
            grupo_api.metrics.http_code_target(elbv2.HttpCodeTarget.TARGET_5XX_COUNT,
                                               period=cinco_min, statistic="Sum"),
            10, 1, mayor,
        )
        alarma(
            "alb-errores-5xx",
            "El ALB generó errores 5xx propios (502/503/504): la tarea no respondió o no existe.",
            alb.metrics.http_code_elb(elbv2.HttpCodeElb.ELB_5XX_COUNT, period=cinco_min, statistic="Sum"),
            5, 1, mayor,
        )
        alarma(
            "api-memoria-alta",
            "La tarea de la API usa 90 % o más de su memoria durante 10 minutos: riesgo de que "
            "ECS la reinicie. Considerar subir api_memory.",
            servicio.metric_memory_utilization(period=cinco_min, statistic="Maximum"),
            90, 2, mayor,
        )
        alarma(
            "api-cpu-alta",
            "La tarea de la API usa 90 % o más de CPU durante 15 minutos (p. ej. recalculando "
            "el pronóstico en memoria).",
            servicio.metric_cpu_utilization(period=cinco_min, statistic="Average"),
            90, 3, mayor,
        )

        # Errores registrados por la API (cargas fallidas, excepciones) que no se ven en el ALB.
        errores_log = logs.MetricFilter(
            self, "FiltroErroresApi",
            log_group=logs_api,
            metric_namespace="SAAD",
            metric_name="ErroresApi",
            filter_pattern=logs.FilterPattern.any_term("[ERROR]", "Traceback"),
            metric_value="1",
            default_value=0,
        )
        alarma(
            "api-errores-en-logs",
            "La API registró errores en sus logs (p. ej. falló la carga de un output). Revisar "
            "con: aws logs tail /ecs/saad-api --since 1h",
            errores_log.metric(period=cinco_min, statistic="Sum"),
            1, 1, mayor,
        )
        alarma(
            "cloudfront-errores-5xx",
            "Más del 5 % de las solicitudes a CloudFront terminan en error 5xx durante 10 minutos.",
            distribucion.metric5xx_error_rate(period=cinco_min, statistic="Average"),
            5, 2, mayor,
        )
