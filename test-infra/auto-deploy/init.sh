#!/bin/bash
set -ex

# Deployment configs.
SRC_DIR=$1
REPO_OWNER=$2
PROJECT=$3
WORKER_CLUSTER=$4

ls -R /etc/pod-info

cat /etc/pod-info/annotations
cat /etc/pod-info/labels

# Check out fresh copy of KF and deployment workflow.
# python /usr/local/bin/repo-clone-snapshot.py \
#   --src_dir=${SRC_DIR} \
#   --project=${PROJECT} \
#   --repo_owner=${REPO_OWNER}
# 
# PYTHONPATH="${PYTHONPATH}:${SRC_DIR}/${REPO_OWNER}/testing/py"
# export PYTHONPATH
# 
# # Initiate deployment workflow.
# ${SRC_DIR}/${REPO_OWNER}/testing/test-infra/auto-deploy/workflows.sh \
#   ${SRC_DIR} \
#   ${REPO_OWNER} \
#   ${PROJECT} \
#   ${WORKER_CLUSTER}
