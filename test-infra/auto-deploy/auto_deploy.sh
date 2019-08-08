#!/bin/bash
#
# To run this locally:
# ./auto_deploy.sh --data_dir=/tmp/data --repos='kubeflow/kubeflow;kubeflow/kfctl;jlewi/testing@auto_manual' --project=kubeflow-ci --base_name=kf-vmaster --max_num_cluster=5 --zone=us-east1-b

set -ex

# Include library that helps on argument parsing.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null && pwd)"
. ${DIR}/lib-args.sh

# Deployment configs.
required_args=(data_dir repos project job_labels base_name max_num_cluster zone)

parseArgs $*
validateRequiredArgs ${required_args}

export CLIENT_ID=$(cat /secret/oauth-secret/CLIENT_ID)
export CLIENT_SECRET=$(cat /secret/oauth-secret/CLIENT_SECRET)

# Activate service account auth.
if [ ! -z ${GOOGLE_APPLICATION_CREDENTIALS} ]; then
  gcloud auth activate-service-account --key-file=${GOOGLE_APPLICATION_CREDENTIALS}
  gcloud config list
fi  

export PYTHONPATH="${PYTHONPATH}:/usr/local/bin/py"

# Extract worker job name using checkout_util.
# We make the data dir dependent on the job name.
# This way if the pod exits with an error and gets retried
# it will use the same directory
if [ ! -z ${job_labels} ]; then
  header="from checkout_lib import checkout_util;"
  job_name="checkout_util.get_job_name(\"${job_labels}\")"
  get_job_name="${header} print(${job_name})"
  job_name=$(python -c "${get_job_name}")
  echo job_name=${job_name}
  data_dir=${data_dir}/${job_name}
fi

echo data_dir=${data_dir}

# Get a snapshot of the repos.
python -m checkout_lib.snapshot_kf_deployment \
  --snapshot_repos=${repos} \
  --base_name=${base_name} \
  --project=${project} \
  --job_labels=${job_labels} \
  --data_dir=${data_dir} \
  --max_cluster_num=${max_num_cluster} \
  --github_token_file=${github_token_file}

# Check out fresh copy of KF and deployment workflow.
python -m checkout_lib.repo_clone_snapshot \
  --data_dir=${data_dir}

export PYTHONPATH="${PYTHONPATH}:${data_dir}/testing/py"

# Create the deployment
KUBEFLOW_DIR=${data_dir}/kubeflow
KFCTL_DIR=${data_dir}/kfctl

# Directory where apps should be checked out.
APPS_DIR=${data_dir}

# Trigger create_kf_instance.
python -m kubeflow.testing.create_kf_instance \
  --kubeflow_repo=${KUBEFLOW_DIR} \
  --kfctl_repo=${KFCTL_DIR} \
  --apps_dir=${APPS_DIR} \
  --project=${project} \
  --snapshot_file=${data_dir}/snapshot.json \
  --zone=${zone}

# TODO(gabrielwen): Push changes to app folders to git.
