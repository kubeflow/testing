#!/usr/bin/env bash
# 
# this script assumes the following
#  - PipelineResource of type git for kubeflow is mounted at /workspace/kubeflow
#  - PipelineResource of type git for manifests is mounted at /workspace/manifests
# 
# and expects the following:
# env-vars:
#   namespace
#   image_name (eg centraldashboard)
#   kubeflow_repo_revision
#   kubeflow_repo_url
# secrets:
#   gcp-credentials
#   github-token
#   github-ssh
#   kubeflow-oauth
# 
# The script does the following in the kubeflow manifests repo
# - edits the image tag in the kustomization.yaml (its workingdir is where the component's manifest is)
# - calls `make generate; make test` under manifests/tests 
# - if successful 
#   - commits the changes 
#   - creates a PR.
#
# how to set env vars from configmap if debugging
# for i in $(kubectl get cm ci-pipeline-run-parameters -ojson | jq -r '.data | keys[] as $k | "\($k)=\(.[$k])"'); do echo export $i; export $i; done
#
set -ex

# This is for debug
echo '--env--'
env | sort
echo '--env--'

# GitHub user to store the fork
fork_user=kubeflow-bot

# Get the commit for the kubeflow repository
cd /workspace/kubeflow
kubeflow_commit=$(git rev-parse HEAD)
kubeflow_commit=${kubeflow_commit:0:8}

image_tag=$(echo ${IMAGE_URL} | cut -d':' -f 2)
new_branch_name='update_'$image_name'_'${image_tag}

# Tekton will automatically mount the ssh private key and known hosts stored in the git secret
# in /tekton/home/.ssh
# however since this scriptt runs in our test worker image  it ends up using /root/.sssh
ln -sf /tekton/home/.ssh /root/.ssh
ssh-keyscan -t rsa github.com > /root/.ssh/known_hosts
cd /workspace/manifests

# Do a full fetch to unshallow the clone
# it looks like Tekton might do a shallow checkout
git fetch --unshallow

# Create a new branch for the pull request
git checkout -b $new_branch_name origin/${MANIFESTS_REPO_REVISION}

# Add the kubeflow-bot repo
git remote add ${fork_user} git@github.com:${fork_user}/manifests.git

cd /workspace/manifests/${PATH_TO_MANIFESTS_DIR}
kustomize edit set image ${SRC_IMAGE_URL}=${IMAGE_URL}
cd /workspace/manifests/tests

make generate-changed-only 
make test
if (( $? == 0 )); then
  git config --global user.email "kubeflow-bot@kubflow.org"
  git config --global user.name "kubeflow-bot"
  
  tmpfile=$(mktemp)
  
  echo "[auto PR] Update the ${image_name} image to commit ${image_tag}" > $tmpfile
  echo "" >> $tmpfile
  echo "* image ${image_url}" >> $tmpfile  

  echo "" >> $tmpfile
  echo "" >> $tmpfile
  # TODO(jlewi): We shouldn't hardcode the repository name. We can parse kubeflow_repo_url
  # This will be easier to do once we rewrite this in python.
  echo "* Image built from kubeflow/kubeflow@$(kubeflow_commit)" >> $tmpfile

  git commit -a -F ${tmpfile}
  
  git push ${fork_user} $new_branch_name -f
  hub pull-request -f -b 'kubeflow:master' -F $tmpfile
else
  echo 'make generate && make test' failed
fi
