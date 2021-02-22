"""
The python file defines all the CFN stack needs to be created
in AWS resource level.

Note: given the restraints of one EKS cluster per CFN stack,
we have to create same number of CFN stacks with respect to
EKS clusters.
"""

from aws_cdk import core, aws_eks, aws_s3, aws_ecr, aws_iam, aws_certificatemanager
from config.static_config.S3_Resources import S3_Bucket_List
from config.static_config.ECR_Resources import ECR_Private_Registry_List
from config.static_config.EKS_Resources import EKS_Cluster_List
from config.static_config.IAM_Resources import IAM_Role_List
from config.static_config.ACM_Resources import ACM_Certs_List


class CDKS3Stack(core.Stack):
    """CDK Class for S3_Resources.py buckets"""

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        # Define S3_Resources.py buckets
        for cdk_id, bucket_name in S3_Bucket_List.items():
            aws_s3.Bucket(
                self,
                cdk_id,
                bucket_name=bucket_name,
                removal_policy=core.RemovalPolicy.DESTROY,
            )


class CDKECRStack(core.Stack):
    """CDK Class for ECR registries"""

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # Define ECR Registries
        for cdk_id, registry_name in ECR_Private_Registry_List.items():
            aws_ecr.Repository(
                self,
                cdk_id,
                repository_name=registry_name,
                removal_policy=core.RemovalPolicy.DESTROY,
            )


class CDKIAMRolesStack(core.Stack):
    """CDK Class for IAM roles"""

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define IAM Roles
        for cdk_id, role_name in IAM_Role_List.items():
            aws_iam.Role(
                self,
                cdk_id,
                role_name=role_name,
                assumed_by=aws_iam.ServicePrincipal("eks.amazonaws.com"),
            )


class CDKACMCertsStack(core.Stack):
    """CDK Class for ACM certs"""

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # Define ACM Certs
        for cdk_id, (domain_name, validation_method) in ACM_Certs_List.items():
            aws_certificatemanager.Certificate(
                self,
                cdk_id,
                domain_name=domain_name,
                validation_method=validation_method,
            )


class CDKEKSClusterStack(core.Stack):
    """CDK Class for basic EKS Cluster"""

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        cdk_id = self.cdk_id
        ng_cdk_id = self.ng_cdk_id
        if cdk_id not in EKS_Cluster_List:
            return
        cluster_config, worker_node_config = EKS_Cluster_List[cdk_id]
        cluster_name, k8s_version = cluster_config
        instance_type, min_size, max_size, desired_size, disk_size = worker_node_config

        cluster = aws_eks.Cluster(
            self,
            cdk_id,
            version=k8s_version,
            default_capacity=0,
            cluster_name=cluster_name,
        )
        cluster.add_nodegroup_capacity(
            ng_cdk_id,
            instance_types=[instance_type],
            min_size=min_size,
            max_size=max_size,
            desired_size=desired_size,
            disk_size=disk_size,
        )


class CDKProwClusterStack(CDKEKSClusterStack):
    """CDK Class for Prow EKS cluster"""

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        self.cdk_id = "prow_cluster"
        self.ng_cdk_id = "custom-prow-node-group"
        super().__init__(scope, construct_id, **kwargs)


class CDKArgoClusterStack(CDKEKSClusterStack):
    """CDK Class for Argo EKS cluster"""

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        self.cdk_id = "argo_cluster"
        self.ng_cdk_id = "custom-argo-node-group"
        super().__init__(scope, construct_id, **kwargs)


class CDKTektonClusterStack(CDKEKSClusterStack):
    """CDK Class for Tekton EKS cluster"""

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        self.cdk_id = "tekton_cluster"
        self.ng_cdk_id = "custom-tekton-node-group"
        super().__init__(scope, construct_id, **kwargs)


class CDKWorkerClusterStack(CDKEKSClusterStack):
    """CDK Class for Daily Worker EKS cluster"""

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        self.cdk_id = "worker_cluster"
        self.ng_cdk_id = "custom-worker-node-group"
        super().__init__(scope, construct_id, **kwargs)
