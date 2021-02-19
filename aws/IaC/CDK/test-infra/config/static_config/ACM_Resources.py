"""
This file defines ACM resource static configuration parameters for CDK Constructs
"""
from aws_cdk import aws_certificatemanager

ACM_Certs_List = {
    # Pattern
    # "cdk-id": ("domain-name", "validation-method")
    # Example:

    # "cdk-poc": (
    #     "cdk-poc.kubeflow-testing.com",
    #     aws_certificatemanager.ValidationMethod.DNS,
    # )
}
