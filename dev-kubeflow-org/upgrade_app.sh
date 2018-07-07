#!/bin/bash
#
# A simple script to recreate the Kubeflow app for kubeflow-dev.
# The purpose of this script is to make it easy to pull in the latest
# release.
#
# By design this script doesn't actually modify the current deployment
# (e.g. delete the current namespace or apply the deployment)
set -ex
# Create a namespace for kubeflow deployment
NAMESPACE=kubeflow

# Which version of Kubeflow to use
# For a list of releases refer to:
# https://github.com/kubeflow/kubeflow/releases
VERSION=master
API_VERSION=v1.7.0

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
GIT_ROOT="$(git rev-parse --show-toplevel)"
cd ${DIR}

APP_NAME=ks-app
APP_DIR=${DIR}/${APP_NAME}
cd ${APP_NAME}

# TODO(jlewi): Right now we are assuming the Kubeflow repository
# is checked out as git_kubeflow and we use that to get the upgrade
# script. We need a better solution. Should we download it via
# curl/wget once its committed.
DEFAULT_KUBEFLOW_DIR="$(cd ${GIT_ROOT}/../git_kubeflow && pwd)"
KUBEFLOW_DIR=${KUBEFLOW_DIR:-${DEFAULT_KUBEFLOW_DIR}}

REGISTRY=github.com/kubeflow/kubeflow/tree/v0.2-branch/kubeflow

# TODO(jlewi): We might want to specify the registry version.
python ${KUBEFLOW_DIR}/scripts/upgrade_ks_app.py \
	--app_dir=${APP_DIR} \
	--registry=${REGISTRY}

# Remove components so we can regenerate them from the updated
# prototypes
ks component rm kubeflow-core
ks component rm cert-manager
ks component rm iap-ingress
ks component rm katib

# Create templates for core components
ks generate kubeflow-core kubeflow-core

# Setup ingress
ACCOUNT=google-kubeflow-team@google.com
FQDN=dev.kubeflow.org
IP_NAME="kubeflow-tf-hub"
ks generate cert-manager cert-manager --acmeEmail=${ACCOUNT}
ks generate iap-ingress iap-ingress --namespace=${NAMESPACE} \
       --ipName=${IP_NAME} \
       --hostname="${FQDN}" \
       --oauthSecretName="kubeflow-oauth"

# Create katib components
ks generate katib katib

ks param set kubeflow-core jupyterHubAuthenticator iap

# Enable collection of anonymous usage metrics
# Skip this step if you don't want to enable collection.
#
# We use the same usage id on redeployments so we won't conflate
# redeployments with unique clusters.
USAGE_ID=f85740a3-5f60-4146-91b6-2ab7089cf01c
ks param set kubeflow-core reportUsage true
ks param set kubeflow-core usageId ${USAGE_ID}

# Set the name of the PD for backing a NFS to hold github issue
# summarization model data
ks param set kubeflow-core disks github-issues-data --env=default

# Enable a PVC backed by the default StorageClass
ks param set kubeflow-core jupyterNotebookPVCMount /home/jovyan --env=default

# Run autoformat from the git root	
cd ${GIT_ROOT}	
bash <(curl -s https://raw.githubusercontent.com/kubeflow/kubeflow/${VERSION}/scripts/autoformat_jsonnet.sh)