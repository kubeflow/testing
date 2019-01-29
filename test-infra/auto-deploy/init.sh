#!/bin/bash
set -ex

# Deployment configs.
SRC_DIR=$1
REPO_OWNER=$2
PROJECT=$3
WORKER_CLUSTER=$4

env

# Check out fresh copy of KF and deployment workflow.
# TODO(gabrielwen): Need to make a seperate workflow to snapshot repos.
/usr/local/bin/checkout.sh ${SRC_DIR} ${REPO_OWNER} kubeflow
git clone git@github.com:gabrielwen/testing.git --branch snapshot-cron --single-branch
# /usr/local/bin/checkout.sh ${SRC_DIR} ${REPO_OWNER} testing

PYTHONPATH="${PYTHONPATH}:${SRC_DIR}/${REPO_OWNER}/testing/py"
export PYTHONPATH

# Initiate deployment workflow.
${SRC_DIR}/${REPO_OWNER}/testing/test-infra/auto-deploy/workflows.sh \
  ${SRC_DIR} \
  ${REPO_OWNER} \
  ${PROJECT} \
  ${WORKER_CLUSTER}
