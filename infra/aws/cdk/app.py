#!/usr/bin/env python3
"""Aplicación CDK del SAAD. Ver infra/aws/cdk/README.md."""

import os

import aws_cdk as cdk

from saad_stack import SaadStack

app = cdk.App()
SaadStack(
    app, "Saad",
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region="us-east-1"),
    description="SAAD: API en ECS Fargate, sitio en S3 y CloudFront",
)
cdk.Tags.of(app).add("proyecto", "saad")
app.synth()
