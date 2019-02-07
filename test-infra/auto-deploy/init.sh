#!/bin/bash
set -ex

# Deployment configs.
SRC_DIR=$1
REPO_OWNER=$2
PROJECT=$3
WORKER_CLUSTER=$4
JOB_LABELS=$5
NFS_MNT=$6

# Activate service account auth.
export GOOGLE_APPLICATION_CREDENTIALS=/secret/gcp-credentials/key.json
gcloud auth activate-service-account --key-file=${GOOGLE_APPLICATION_CREDENTIALS}
gcloud config list

# export PYTHONPATH="${PYTHONPATH}:/usr/local/bin/py"
# 
# python -m checkout_lib.snapshot_kf_deployment \
#   kubeflow testing \
#   --project=${PROJECT} \
#   --repo_owner=${REPO_OWNER} \
#   --job_labels=${JOB_LABELS} \
#   --nfs_path=${NFS_MNT}
# 
# DEPLOYMENT_METADATA=${SRC_DIR}/deployment_metadata.json
# 
# # Check out fresh copy of KF and deployment workflow.
# python -m checkout_lib.repo_clone_snapshot \
#   --src_dir=${SRC_DIR} \
#   --project=${PROJECT} \
#   --repo_owner=${REPO_OWNER} \
#   --job_labels=${JOB_LABELS} \
#   --nfs_path=${NFS_MNT}

# TODO(gabrielwen): Remove this before sending for review.
# rm -rf ${SRC_DIR}/${REPO_OWNER}/testing
mkdir -p ${SRC_DIR}/${REPO_OWNER}
git clone --single-branch --branch cluster-label \
  https://github.com/gabrielwen/testing.git ${SRC_DIR}/${REPO_OWNER}/testing

PYTHONPATH="${PYTHONPATH}:${SRC_DIR}/${REPO_OWNER}/testing/py"
export PYTHONPATH="${PYTHONPATH}:${SRC_DIR}/${REPO_OWNER}/testing/test-infra/auto-deploy"

python -m checkout_lib.snapshot_kf_deployment \
  kubeflow testing \
  --project=${PROJECT} \
  --repo_owner=${REPO_OWNER} \
  --job_labels=${JOB_LABELS} \
  --nfs_path=${NFS_MNT}

# Initiate deployment workflow.
# ${SRC_DIR}/${REPO_OWNER}/testing/test-infra/auto-deploy/workflows.sh \
#   ${SRC_DIR} \
#   ${REPO_OWNER} \
#   ${PROJECT} \
#   ${WORKER_CLUSTER} \
#   ${JOB_LABELS} \
#   ${NFS_MNT}
