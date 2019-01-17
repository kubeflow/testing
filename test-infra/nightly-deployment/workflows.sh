#!/bin/bash
#
# This script is meant to be the entrypoint for a prow job.
# It checkos out a repo and then looks for prow_config.yaml in that
# repo and uses that to run one or more workflows.
set -ex

SRC_DIR=/src
REPO_OWNER=kubeflow

# Check out repos we need.
/usr/local/bin/checkout.sh ${SRC_DIR} ${REPO_OWNER} kubeflow
/usr/local/bin/checkout.sh ${SRC_DIR} ${REPO_OWNER} testing

# TODO(gabrielwen): Do we need to use key.json?
# export GOOGLE_APPLICATION_CREDENTIALS=/secret/gcp-credentials/key.json

rm -rf /src/kubeflow/testing/test-infra/kf-v0-4-n00

gcloud container clusters get-credentials gabrielwen-playground \
  --zone us-east1-d \
  --project gabrielwen-learning

# Trigger create_kf_instance.
# python -m kubeflow.testing.create_kf_instance \
#   --base=kf-v0-4 \
#   --kubeflow_repo=/src/kubeflow/kubeflow \
#   --apps_dir=/src/kubeflow/testing/test-infra \
#   --project=gabrielwen-learning \
#   --oauth_file=gs://deployment-worker-data/kf-iap-oauth.gabrielwen-learning.yaml
