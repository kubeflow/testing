#!/usr/bin/env python3

from aws_cdk import core

from test_infra.test_infra_stack import (
    CDKS3Stack,
    CDKECRStack,
    CDKACMCertsStack,
    CDKArgoClusterStack,
    CDKIAMRolesStack,
    CDKProwClusterStack,
    CDKTektonClusterStack,
    CDKWorkerClusterStack,
    env,
)

app = core.App()

# Reference CDK Stacks
CDKS3Stack(app, "cdk-s3")
CDKECRStack(app, "cdk-ecr")
CDKACMCertsStack(app, "cdk-acm")
CDKIAMRolesStack(app, "cdk-iam-roles")

CDKArgoClusterStack(app, "cdk-eks-argo", env=env)
CDKProwClusterStack(app, "cdk-eks-prow", env=env)
CDKTektonClusterStack(app, "cdk-eks-tekton", env=env)
CDKWorkerClusterStack(app, "cdk-eks-worker", env=env)

app.synth()
