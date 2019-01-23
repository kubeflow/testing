#!/bin/bash
#
# This script is meant to be the entrypoint for a prow job.
# It checkos out a repo and then looks for prow_config.yaml in that
# repo and uses that to run one or more workflows.
set -ex

SRC_DIR=$1
REPO_OWNER=$2
PROJECT=$3
WORKER_CLUSTER=$4

# Check out repos we need.
# TODO(gabrielwen): Need to make a seperate workflow to snapshot repos.
${SRC_DIR}/${REPO_OWNER}/testing/test-infra/auto-deploy/checkout.sh \
  ${SRC_DIR} ${REPO_OWNER} kubeflow

# Activate service account auth.
export GOOGLE_APPLICATION_CREDENTIALS=/secret/gcp-credentials/key.json
gcloud auth activate-service-account --key-file=${GOOGLE_APPLICATION_CREDENTIALS}
gcloud config list

APPS_DIR=${SRC_DIR}/${REPO_OWNER}/testing/test-infra
KF_DIR=${SRC_DIR}/${REPO_OWNER}/kubeflow

# Trigger create_kf_instance.
python -m kubeflow.testing.create_kf_instance \
  --base=kf-v0-4 \
  --kubeflow_repo=${KF_DIR} \
  --apps_dir=${APPS_DIR} \
  --project=${PROJECT} \
  --deployment_worker_cluster=${WORKER_CLUSTER}

# TODO(gabrielwen): Push changes to app folders to git.
