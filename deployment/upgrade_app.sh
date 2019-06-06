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
  APP_NAME=kubeflow-latest-kust-app
  FQDN=dev-latest.kubeflow.org
  IP_NAME="kubeflow-latest-ip"
  USAGE_ID=a9cfe6c1-0e75-44aa-8fc0-a44db63611dc
elif [ "$1" = "stable" ]
then
  # Which version of Kubeflow to use
  # For a list of releases refer to:
  # https://github.com/kubeflow/kubeflow/releases
  VERSION="v0.2.2"
  NAMESPACE=kubeflow
  APP_NAME=kf-kust-app
  FQDN=dev.kubeflow.org
  IP_NAME="kubeflow-tf-hub"
  USAGE_ID=f85740a3-5f60-4146-91b6-2ab7089cf01c
else
  echo "Must specify either 'latest' or 'stable'"
  exit -1	
fi

KUBEFLOW_CLOUD="gke"
ZONE=${ZONE:-$(gcloud config get-value compute/zone 2>/dev/null)}
ZONE=${ZONE:-"us-central1-a"}
GCFS_INSTANCE=${GCFS_INSTANCE:-"${DEPLOYMENT_NAME}"}
GCFS_STORAGE=${GCFS_STORAGE:-"1T"}
GCFS_INSTANCE_IP_ADDRESS=$(gcloud beta filestore instances describe \
  ${GCFS_INSTANCE} --location ${ZONE} | \
  grep --after-context=1 ipAddresses | \
  tail -1 | \
  awk '{print $2}')

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
GIT_ROOT="$(git rev-parse --show-toplevel)"
cd ${DIR}

APP_DIR=${DIR}/${APP_NAME}
cd ${APP_NAME}

REGISTRY=github.com/kubeflow/kubeflow/tree/${VERSION}/kubeflow

python <(curl -s https://raw.githubusercontent.com/kubeflow/kubeflow/${VERSION}/scripts/upgrade_kf_kust_app.py) \
	--app_dir=${APP_DIR} \
	--registry=${REGISTRY}

# Remove components so we can regenerate them from the updated
# prototypes
ks component rm google-cloud-filestore-pv
ks component rm pytorch-operator
ks component rm jupyterhub
ks component rm ambassador
ks component rm centraldashboard
ks component rm tf-job-operator
ks component rm spartakus
ks component rm cert-manager
ks component rm iap-ingress

# Install all required packages
set +e
ks pkg install kubeflow/argo
ks pkg install kubeflow/core
ks pkg install kubeflow/examples
ks pkg install kubeflow/katib
ks pkg install kubeflow/mpi-job
ks pkg install kubeflow/pytorch-job
ks pkg install kubeflow/seldon
ks pkg install kubeflow/tf-serving
set -e

# Create templates for core components
ks generate google-cloud-filestore-pv google-cloud-filestore-pv --name="kubeflow-gcfs" --storageCapacity="${GCFS_STORAGE}" --serverIP="${GCFS_INSTANCE_IP_ADDRESS}"
ks generate pytorch-operator pytorch-operator
ks generate ambassador ambassador --ambassadorImage="gcr.io/kubeflow-images-public/ambassador:0.30.1" --statsdImage="gcr.io/kubeflow-images-public/statsd:0.30.1" --cloud=${KUBEFLOW_CLOUD}
ks generate jupyterhub jupyterhub --cloud=${KUBEFLOW_CLOUD} --disks="kubeflow-gcfs"
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
ks param set spartakus reportUsage true
ks param set spartakus usageId ${USAGE_ID}

# Run autoformat from the git root	
cd ${GIT_ROOT}	
bash <(curl -s https://raw.githubusercontent.com/kubeflow/kubeflow/${VERSION}/scripts/autoformat_jsonnet.sh)
