#!/bin/bash
#
# This script is meant to be the entrypoint for a prow job.
# It checkos out a repo and then looks for prow_config.yaml in that
# repo and uses that to run one or more workflows.
set -ex

# Checkout the code.
/usr/local/bin/checkout.sh /src

# Trigger a workflow
if [ -z "$CLOUD_PROVIDER" ] ||  [ "$CLOUD_PROVIDER" = "gcp" ]
then
  python -m kubeflow.testing.run_e2e_workflow \
    --project=kubeflow-ci \
    --zone=us-east1-d \
    --cluster=kubeflow-testing \
    --bucket=kubernetes-jenkins \
    --config_file=/src/${REPO_OWNER}/${REPO_NAME}/prow_config.yaml \
    --repos_dir=/src
else
  if [[ "$CLOUD_PROVIDER" == "aws" ]]
  then
    echo "Triggering AWS Argo Workflows"
    python -m kubeflow.testing.run_e2e_workflow \
      --cluster=${AWS_EKS_CLUSTER:-"kubeflow-prow-dev-test"} \
      --bucket=${ARTIFACTS_S3_BUCKET:-"aws-kubernetes-jenkins"} \
      --config_file=/src/${REPO_OWNER}/${REPO_NAME}/prow_config.yaml \
      --repos_dir=/src \
      --cloud_provider=aws \
      --aws_region=${AWS_DEFAULT_REGION:-"us-west-2"}
  fi
fi