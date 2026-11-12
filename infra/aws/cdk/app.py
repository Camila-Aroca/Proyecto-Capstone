#!/usr/bin/env python3
"""Aplicación CDK del SAAD. Ver infra/aws/cdk/README.md.

- `Saad`: el despliegue (API en ECS Fargate, sitio en S3 y CloudFront). Se sintetiza solo
  si se entrega `api_tag`, que es obligatorio para él; así `cdk deploy SaadCi` no lo exige.
- `SaadCi`: CodePipeline y CodeBuild que verifican y despliegan `Saad`.
"""

import os

import aws_cdk as cdk

from ci_stack import SaadCiStack
from saad_stack import SaadStack

app = cdk.App()
# En la verificación de CI se sintetiza sin cuenta, para no necesitar permisos de consulta.
cuenta = None if os.environ.get("SAAD_SINTESIS_SIN_CUENTA") else os.environ.get("CDK_DEFAULT_ACCOUNT")
entorno = cdk.Environment(account=cuenta, region="us-east-1")

if app.node.try_get_context("api_tag"):
    SaadStack(app, "Saad", env=entorno, description="SAAD: API en ECS Fargate, sitio en S3 y CloudFront")
SaadCiStack(app, "SaadCi", env=entorno, description="SAAD: CodePipeline y CodeBuild para verificar y desplegar")

cdk.Tags.of(app).add("proyecto", "saad")
app.synth()
