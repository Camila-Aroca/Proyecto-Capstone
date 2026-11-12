"""Pila CDK de integración y despliegue continuo del SAAD con CodePipeline y CodeBuild.

- Conexión de CodeConnections con GitHub. Se crea en estado PENDING: hay que activarla una
  vez en la consola (Developer Tools → Settings → Connections) instalando la app
  "AWS Connector for GitHub" en la cuenta dueña del repositorio.
- CodeBuild `saad-verificar` (infra/aws/buildspecs/verificar.yml): tests de Python,
  síntesis de la plantilla con CDK y cfn-lint. No usa la cuenta de AWS más que para logs.
- CodeBuild `saad-desplegar` (infra/aws/buildspecs/desplegar.yml): construye el frontend y
  ejecuta `cdk deploy Saad`, que despliega la plantilla en CloudFormation. Conserva la
  imagen y la configuración de la API que están en servicio.
- Pipeline `saad-despliegue`: push a `main` que toque infraestructura o frontend →
  verificar → desplegar.
- Pipeline `saad-pr`: cada pull request hacia `main` → verificar (CI del issue #64).

Datos que no van en el repositorio, en Parameter Store (se crean una vez a mano):
- `/saad/origin-secret` (SecureString): encabezado secreto CloudFront → ALB.
- `/saad/alarm-email` (String): correo de las alarmas.

Contexto: `github_owner` y `github_repo` (por defecto Camila-Aroca/Proyecto-Capstone).
"""

from __future__ import annotations

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as actions,
    aws_codestarconnections as connections,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct

RAMA = "main"
# Cambios que justifican redesplegar la pila: infraestructura y sitio. El código de la API
# llega como imagen nueva (publicar_imagen.sh), no por este pipeline.
RUTAS_DESPLIEGUE = ["infra/aws/**", "frontend/**"]
PARAMETRO_SECRETO = "/saad/origin-secret"
PARAMETRO_CORREO = "/saad/alarm-email"
CALIFICADOR_CDK = "hnb659fds"  # calificador por defecto de `cdk bootstrap`


class SaadCiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        owner = self.node.try_get_context("github_owner") or "Camila-Aroca"
        repo = self.node.try_get_context("github_repo") or "Proyecto-Capstone"

        conexion = connections.CfnConnection(
            self, "ConexionGithub", connection_name="saad-github", provider_type="GitHub",
        )

        entorno_build = codebuild.BuildEnvironment(
            build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
            compute_type=codebuild.ComputeType.SMALL,
        )

        def proyecto(id_: str, nombre: str, buildspec: str, descripcion: str,
                     variables: dict[str, codebuild.BuildEnvironmentVariable] | None = None,
                     ) -> codebuild.PipelineProject:
            return codebuild.PipelineProject(
                self, id_,
                project_name=nombre,
                description=descripcion,
                build_spec=codebuild.BuildSpec.from_source_filename(buildspec),
                environment=entorno_build,
                environment_variables=variables,
                timeout=Duration.minutes(30),
                logging=codebuild.LoggingOptions(cloud_watch=codebuild.CloudWatchLoggingOptions(
                    log_group=logs.LogGroup(
                        self, f"Logs{id_}",
                        log_group_name=f"/codebuild/{nombre}",
                        retention=logs.RetentionDays.TWO_WEEKS,
                        removal_policy=RemovalPolicy.DESTROY,
                    ),
                )),
            )

        verificar = proyecto(
            "Verificar", "saad-verificar", "infra/aws/buildspecs/verificar.yml",
            "Tests de Python, síntesis CDK y cfn-lint de la plantilla del SAAD.",
        )
        desplegar = proyecto(
            "Desplegar", "saad-desplegar", "infra/aws/buildspecs/desplegar.yml",
            "Construye el frontend y despliega la pila Saad en CloudFormation con CDK.",
            variables={
                "SAAD_ORIGIN_SECRET": codebuild.BuildEnvironmentVariable(
                    type=codebuild.BuildEnvironmentVariableType.PARAMETER_STORE, value=PARAMETRO_SECRETO),
                "SAAD_ALARM_EMAIL": codebuild.BuildEnvironmentVariable(
                    type=codebuild.BuildEnvironmentVariableType.PARAMETER_STORE, value=PARAMETRO_CORREO),
            },
        )
        # `cdk deploy` no despliega con los permisos del build: asume los roles que creó
        # `cdk bootstrap`, que ya tienen los permisos de CloudFormation y de publicación de assets.
        desplegar.add_to_role_policy(iam.PolicyStatement(
            actions=["sts:AssumeRole"],
            resources=[f"arn:aws:iam::{self.account}:role/cdk-{CALIFICADOR_CDK}-*-{self.account}-{self.region}"],
        ))
        # Lecturas para conservar la configuración en servicio y resolver la prefix list.
        desplegar.add_to_role_policy(iam.PolicyStatement(
            actions=["ecs:DescribeServices", "ecs:DescribeTaskDefinition",
                     "ec2:DescribeManagedPrefixLists", "cloudformation:DescribeStacks"],
            resources=["*"],
        ))

        def fuente(nombre: str, salida: codepipeline.Artifact) -> actions.CodeStarConnectionsSourceAction:
            return actions.CodeStarConnectionsSourceAction(
                action_name=nombre,
                owner=owner,
                repo=repo,
                branch=RAMA,
                connection_arn=conexion.attr_connection_arn,
                output=salida,
                trigger_on_push=False,  # los disparadores se definen en el pipeline (V2)
            )

        # --- Despliegue continuo: main → verificar → desplegar --------------------------
        codigo = codepipeline.Artifact("Codigo")
        origen = fuente("GitHub", codigo)
        despliegue = codepipeline.Pipeline(
            self, "PipelineDespliegue",
            pipeline_name="saad-despliegue",
            pipeline_type=codepipeline.PipelineType.V2,
            execution_mode=codepipeline.ExecutionMode.QUEUED,
            restart_execution_on_update=False,
            cross_account_keys=False,  # una sola cuenta: sin llaves KMS (US$1/mes cada una)
            stages=[
                codepipeline.StageProps(stage_name="Fuente", actions=[origen]),
                codepipeline.StageProps(stage_name="Verificar", actions=[actions.CodeBuildAction(
                    action_name="Tests-y-cfn-lint", project=verificar, input=codigo)]),
                codepipeline.StageProps(stage_name="Desplegar", actions=[actions.CodeBuildAction(
                    action_name="CloudFormation", project=desplegar, input=codigo)]),
            ],
            triggers=[codepipeline.TriggerProps(
                provider_type=codepipeline.ProviderType.CODE_STAR_SOURCE_CONNECTION,
                git_configuration=codepipeline.GitConfiguration(
                    source_action=origen,
                    push_filter=[codepipeline.GitPushFilter(
                        branches_includes=[RAMA], file_paths_includes=RUTAS_DESPLIEGUE)],
                ),
            )],
        )

        # --- Integración continua: cada pull request → verificar ------------------------
        codigo_pr = codepipeline.Artifact("CodigoPr")
        origen_pr = fuente("GitHub", codigo_pr)
        pr = codepipeline.Pipeline(
            self, "PipelinePr",
            pipeline_name="saad-pr",
            pipeline_type=codepipeline.PipelineType.V2,
            execution_mode=codepipeline.ExecutionMode.PARALLEL,
            restart_execution_on_update=False,
            cross_account_keys=False,  # una sola cuenta: sin llaves KMS (US$1/mes cada una)
            stages=[
                codepipeline.StageProps(stage_name="Fuente", actions=[origen_pr]),
                codepipeline.StageProps(stage_name="Verificar", actions=[actions.CodeBuildAction(
                    action_name="Tests-y-cfn-lint", project=verificar, input=codigo_pr)]),
            ],
            triggers=[codepipeline.TriggerProps(
                provider_type=codepipeline.ProviderType.CODE_STAR_SOURCE_CONNECTION,
                git_configuration=codepipeline.GitConfiguration(
                    source_action=origen_pr,
                    pull_request_filter=[codepipeline.GitPullRequestFilter(
                        branches_includes=[RAMA],
                        events=[codepipeline.GitPullRequestEvent.OPEN, codepipeline.GitPullRequestEvent.UPDATED],
                    )],
                ),
            )],
        )

        CfnOutput(self, "ConexionArn", value=conexion.attr_connection_arn,
                  description="Activar en la consola antes del primer uso (estado PENDING).")
        CfnOutput(self, "PipelineDespliegueNombre", value=despliegue.pipeline_name)
        CfnOutput(self, "PipelinePrNombre", value=pr.pipeline_name)
