"""
This file defines ECR resource static configuration parameters for CDK Constructs
"""

ECR_Private_Registry_List = {
    # Pattern
    # "cdk-id": "registry-name"

    # Katib images.
    # Katib main components.
    "katib-controller": "katib/v1beta1/katib-controller",
    "katib-db-manager": "katib/v1beta1/katib-db-manager",
    "katib-ui": "katib/v1beta1/katib-ui",
    "katib-cert-generator": "katib/v1beta1/cert-generator",
    # Katib Metric Collector list.
    "katib-file-metrics-collector": "katib/v1beta1/file-metrics-collector",
    "katib-tfevent-metrics-collector": "katib/v1beta1/tfevent-metrics-collector",
    # Katib Suggestion list.
    "katib-suggestion-hyperopt": "katib/v1beta1/suggestion-hyperopt",
    "katib-suggestion-chocolate": "katib/v1beta1/suggestion-chocolate",
    "katib-suggestion-skopt": "katib/v1beta1/suggestion-skopt",
    "katib-suggestion-hyperband": "katib/v1beta1/suggestion-hyperband",
    "katib-suggestion-goptuna": "katib/v1beta1/suggestion-goptuna",
    "katib-suggestion-optuna": "katib/v1beta1/suggestion-optuna",
    "katib-suggestion-enas": "katib/v1beta1/suggestion-enas",
    "katib-suggestion-darts": "katib/v1beta1/suggestion-darts",
    # Katib Early Stopping list.
    "katib-earlystopping-medianstop": "katib/v1beta1/earlystopping-medianstop",
    # Katib Trial list.
    "katib-trial-mxnet-mnist": "katib/v1beta1/trial-mxnet-mnist",
    "katib-trial-pytorch-mnist": "katib/v1beta1/trial-pytorch-mnist",
    "katib-trial-enas-cnn-cifar10-gpu": "katib/v1beta1/trial-enas-cnn-cifar10-gpu",
    "katib-trial-enas-cnn-cifar10-cpu": "katib/v1beta1/trial-enas-cnn-cifar10-cpu",
    "katib-trial-darts-cnn-cifar10": "katib/v1beta1/trial-darts-cnn-cifar10",
    # Training operator
    "training-operator": "training-operator",
}
