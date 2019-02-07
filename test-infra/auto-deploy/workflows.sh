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
JOB_LABELS=$5
NFS_MNT=$6

APPS_DIR=${SRC_DIR}/${REPO_OWNER}/testing/test-infra
KF_DIR=${SRC_DIR}/${REPO_OWNER}/kubeflow

# Extract worker job name using checkout_util.
header="from checkout_lib import checkout_util;"
job_name="checkout_util.get_job_name(\"${JOB_LABELS}\")"
get_job_name="${header} print(${job_name})"
job_name=$(python -c "${get_job_name}")

# Load snapshot JSON.
get_path="checkout_util.get_snapshot_path(\"${NFS_MNT}\", \"${job_name}\")"
get_snapshot_path="${header} print(${get_path})"
snapshot_path=$(python -c "${get_snapshot_path}")

# Extract cluster_num from JSON file.
read_snapshot="cat ${snapshot_path}/snapshot.json"
get_cluster_num="jq .cluster_num"
get_timestamp="jq .timestamp"
cluster_num=$(${read_snapshot} | ${get_cluster_num})
timestamp=$(${read_snapshot} | ${get_timestamp})

# Trigger create_kf_instance.
# python -m kubeflow.testing.create_kf_instance \
#   --base=kf-v0-4 \
#   --kubeflow_repo=${KF_DIR} \
#   --apps_dir=${APPS_DIR} \
#   --project=${PROJECT} \
#   --deployment_worker_cluster=${WORKER_CLUSTER} \
#   --cluster_num=${n} \
#   --timestamp=${timestamp} \
#   --job_name=${job_name}

# TODO(gabrielwen): Push changes to app folders to git.
