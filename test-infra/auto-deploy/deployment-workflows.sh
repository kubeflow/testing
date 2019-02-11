#!/bin/bash
# Workflow used to invoke deployment process.
set -ex

# Include library that helps on argument parsing.
. /usr/local/lib/lib-args.sh

# Deployment configs.
required_args=(src_dir repo_owner project worker_cluster job_labels nfs_mnt \
  base_name)

parseArgs $*
validateRequiredArgs ${required_args}

APPS_DIR=${src_dir}/${repo_owner}/testing/test-infra
KF_DIR=${src_dir}/${repo_owner}/kubeflow

# Extract worker job name using checkout_util.
header="from checkout_lib import checkout_util;"
job_name="checkout_util.get_job_name(\"${job_labels}\")"
get_job_name="${header} print(${job_name})"
job_name=$(python -c "${get_job_name}")

# Load snapshot JSON.
get_path="checkout_util.get_snapshot_path(\"${nfs_mnt}\", \"${job_name}\")"
get_snapshot_path="${header} print(${get_path})"
snapshot_path=$(python -c "${get_snapshot_path}")

# Extract cluster_num from JSON file.
read_snapshot="cat ${snapshot_path}/snapshot.json"
get_cluster_num="jq .cluster_num"
get_timestamp="jq .timestamp"
cluster_num=$(${read_snapshot} | ${get_cluster_num})
timestamp=$(${read_snapshot} | ${get_timestamp})

# Trigger create_kf_instance.
python -m kubeflow.testing.create_kf_instance \
  --base=${base_name} \
  --kubeflow_repo=${KF_DIR} \
  --apps_dir=${APPS_DIR} \
  --project=${project} \
  --deployment_worker_cluster=${worker_cluster} \
  --cluster_num=${cluster_num} \
  --timestamp=${timestamp} \
  --job_name=${job_name}

# TODO(gabrielwen): Push changes to app folders to git.
