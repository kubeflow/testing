#!/bin/bash
set -ex

# Include library that helps on argument parsing.
. /usr/local/lib/lib-args.sh

# Deployment configs.
required_args=(src_dir repo_owner repo_branches project worker_cluster \
  job_labels nfs_mnt base_name max_num_cluster zone)

parseArgs $*
validateRequiredArgs ${required_args}

# Activate service account auth.
gcloud auth activate-service-account --key-file=${GOOGLE_APPLICATION_CREDENTIALS}
gcloud config list

export PYTHONPATH="${PYTHONPATH}:/usr/local/bin/py"

# Split args by comma and replace with space.
repos=$(echo ${repo_branches} | tr "," " ")

python -m checkout_lib.snapshot_kf_deployment \
  ${repos} \
  --base_name=${base_name} \
  --project=${project} \
  --repo_owner=${repo_owner} \
  --job_labels=${job_labels} \
  --nfs_path=${nfs_mnt} \
  --max_cluster_num=${max_num_cluster} \
  --zone=${zone}

# Check out fresh copy of KF and deployment workflow.
python -m checkout_lib.repo_clone_snapshot \
  --src_dir=${src_dir} \
  --project=${project} \
  --repo_owner=${repo_owner} \
  --job_labels=${job_labels} \
  --nfs_path=${nfs_mnt} \
  --zone=${zone}

export PYTHONPATH="${PYTHONPATH}:${src_dir}/${repo_owner}/testing/py"

# Initiate deployment workflow.
${src_dir}/${repo_owner}/testing/test-infra/auto-deploy/deployment-workflows.sh \
  --src_dir=${src_dir} \
  --repo_owner=${repo_owner} \
  --project=${project} \
  --worker_cluster=${worker_cluster} \
  --job_labels=${job_labels} \
  --nfs_mnt=${nfs_mnt} \
  --base_name=${base_name} \
  --zone=${zone}
