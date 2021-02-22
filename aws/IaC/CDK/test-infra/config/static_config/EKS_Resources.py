"""
This file defines EKS resource static configuration parameters for CDK Constructs
"""

from aws_cdk import aws_eks, aws_ec2

EKS_Cluster_List = {
    # Pattern
    # "cdk-id": (("cluster-name", "kubernetes-version"), (instance_type, min_size, max_size, desired_size, disk_size))
    # Example:

    # "prow_cluster": (
    #     ("cdk-poc-prow", aws_eks.KubernetesVersion.V1_18),
    #     (aws_ec2.InstanceType("m5.large"), 2, 4, 2, 20),
    # ),
    # "argo_cluster": (
    #     ("cdk-poc-argo", aws_eks.KubernetesVersion.V1_18),
    #     (aws_ec2.InstanceType("m5.large"), 2, 4, 2, 20),
    # ),
    # "tekton_cluster": (
    #     ("cdk-poc-tekton", aws_eks.KubernetesVersion.V1_18),
    #     (aws_ec2.InstanceType("m5.large"), 2, 4, 2, 20),
    # ),
    # "worker_cluster": (
    #     ("cdk-poc-worker", aws_eks.KubernetesVersion.V1_18),
    #     (aws_ec2.InstanceType("m5.large"), 2, 4, 2, 20),
    # ),
}
