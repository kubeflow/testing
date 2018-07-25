#!/bin/bash
#
# A simple script to recreate the Kubeflow app for kubeflow-dev.
# The purpose of this script is to make it easy to pull in the latest
# release.
#
# By design this script doesn't actually modify the current deployment
# (e.g. delete the current namespace or apply the deployment)
#
# Usage:
#   upgrade_app.sh [latest|stable]
#   - latest points to the master branch
#   - stable points to the last stable release branch
set -ex

API_VERSION=v1.7.0

# Configure parameters for latest and stable environments
if [ "$1" = "latest" ]
then
  VERSION="master"
  NAMESPACE=kubeflow-latest
  APP_NAME=kubeflow-latest_ks_app
  FQDN=dev-latest.kubeflow.org
  IP_NAME="kubeflow-latest-ip"  
elif [ "$1" = "stable" ]
then
  # Which version of Kubeflow to use
  # For a list of releases refer to:
  # https://github.com/kubeflow/kubeflow/releases
  VERSION="v0.2.2"
  NAMESPACE=kubeflow
  APP_NAME=ks-app
  FQDN=dev.kubeflow.org
  IP_NAME="kubeflow-tf-hub"
else
  echo "Must specify either 'latest' or 'stable'"
  exit -1	
fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
GIT_ROOT="$(git rev-parse --show-toplevel)"
cd ${DIR}

APP_DIR=${DIR}/${APP_NAME}
cd ${APP_NAME}

REGISTRY=github.com/kubeflow/kubeflow/tree/${VERSION}/kubeflow

python <(curl -s https://raw.githubusercontent.com/kubeflow/kubeflow/${VERSION}/scripts/upgrade_ks_app.py) \
	--app_dir=${APP_DIR} \
	--registry=${REGISTRY}

# Remove components so we can regenerate them from the updated
# prototypes
ks component rm jupyterhub
ks component rm ambassador
ks component rm centraldashboard
ks component rm tf-job-operator
ks component rm spartakus
ks component rm cert-manager
ks component rm iap-ingress

# Create templates for core components
ks generate jupyterhub jupyterhub
ks generate ambassador ambassador
ks generate centraldashboard centraldashboard
ks generate tf-job-operator tf-job-operator
ks generate spartakus spartakus

# Setup ingress
ACCOUNT=google-kubeflow-team@google.com

ks generate cert-manager cert-manager --acmeEmail=${ACCOUNT}
ks generate iap-ingress iap-ingress --namespace=${NAMESPACE} \
       --ipName=${IP_NAME} \
       --hostname="${FQDN}" \
       --oauthSecretName="kubeflow-oauth"

ks param set jupyterhub jupyterHubAuthenticator iap

# Set the name of the PD for backing a NFS to hold github issue
# summarization model data
ks param set jupyterhub disks github-issues-data --env=default

# Enable a PVC backed by the default StorageClass
ks param set jupyterhub jupyterNotebookPVCMount /home/jovyan --env=default

# Enable collection of anonymous usage metrics
# Skip this step if you don't want to enable collection.
#
# We use the same usage id on redeployments so we won't conflate
# redeployments with unique clusters.
USAGE_ID=a9cfe6c1-0e75-44aa-8fc0-a44db63611dc

ks param set spartakus reportUsage true
ks param set spartakus usageId ${USAGE_ID}

# Run autoformat from the git root	
cd ${GIT_ROOT}	
bash <(curl -s https://raw.githubusercontent.com/kubeflow/kubeflow/${VERSION}/scripts/autoformat_jsonnet.sh)
