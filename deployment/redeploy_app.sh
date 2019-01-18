#!/bin/bash
#
# A helper script to redeploy the app.
#
# The script kicks some pods so that they get upgraded.
#
# Usage:
#   redeploy_app.sh [latest|stable]
#   - latest points to the master branch
#   - stable points to the last stable release branch
set -ex

function runApply() {  
  # https://github.com/kubeflow/kubeflow/issues/980#issuecomment-403245628
  # It looks like optimistic locking will fail and we need to retry.
  # Hopefully this will be fixed in 0.11.1. If not we should consider
  # adding retries.
  ENV=$1
  COMPONENT=$2

  # Retry up to 20 times
  for i in `seq 1 20`;
  do
  	set +e
	ks apply ${ENV} -c ${COMPONENT}
	result=$?
	set -e
	if [[ ${result} -eq 0 ]]; then
		return
	fi
  done
  echo "ks apply didn't succeeed"
  exit -1
}

function applyIapIngress() {  
  # The combination of 
  # https://github.com/kubeflow/kubeflow/issues/1145
  # and 
  # https://github.com/kubeflow/kubeflow/issues/980#
  # Makes it a real pain. To deal with #980 we need
  # to retry ks apply until it succeeds. But
  # because of 1145 we need to delete the service
  # before every retry.

  ENV=$1
  NAMESPACE=$2

  # Retry up to 20 times
  for i in `seq 1 20`;
  do
  	set +e
  	kubectl -n ${NAMESPACE} delete service envoy
	ks apply ${ENV} -c iap-ingress
	result=$?
	set -e
	if [[ ${result} -eq 0 ]]; then
		return
	fi
  done
  echo "ks apply didn't succeeed"
  exit -1
}

# Configure parameters for latest and stable environments
if [[ "$1" == "latest" ]]
then
  NAMESPACE=kubeflow-latest
  APP_NAME=kubeflow-latest_ks_app
  FQDN=dev-latest.kubeflow.org
  IP_NAME="kubeflow-latest-ip"  
elif [[ "$1" == "stable" ]]
then
  NAMESPACE=kubeflow
  APP_NAME=ks-app
  FQDN=dev.kubeflow.org
  IP_NAME="kubeflow-tf-hub"
else
  echo "Must specify either 'latest' or 'stable'"
  exit -1	
fi

# Fetch master information and strip away color markers
KUBE_INFO=$(kubectl cluster-info | sed 's/\x1B\[[0-9;]\+[A-Za-z]//g')

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd ${DIR}/${APP_NAME}

KS_ENV=default
KS_ENV_INFO=$(ks env describe ${KS_ENV})

KS_MASTER=`expr match "${KS_ENV_INFO}" '.*server[^\.0-9]*\([\.0-9]\+\)'`
echo KS_MASTER=${KS_MASTER}
MASTER=`expr match "${KUBE_INFO}" '[^\.0-9]*\([\.0-9]\+\)'`
echo MASTER=${MASTER}

if [[ "${MASTER}" != "${KS_MASTER}" ]]; then
  echo "The current kubectl context doesn't match the ks environment"
  echo "Please configure the context to match ks environment ${KS_ENV}"
  exit -1
else
  echo "kubectl context matches ks environment ${KS_ENV}"
fi

# Delete some confimaps so that will get recreated with the new config.
# TODO(jlewi): If we annotated the objects with a hash of the  config
# would ks apply automatically update them?
set +e
kubectl -n ${NAMESPACE} delete configmap envoy-config
kubectl -n ${NAMESPACE} delete configmap jupyterhub-config
kubectl -n ${NAMESPACE} delete configmap tf-job-operator-config
set -e

set +e
kubectl delete crd tfjobs.kubeflow.org

# Delete nodeort services because running apply on them doesn't
# work see
# https://github.com/kubeflow/kubeflow/issues/1145
kubectl -n ${NAMESPACE} delete service vizier-core
set -e

applyIapIngress ${KS_ENV} ${NAMESPACE}
runApply ${KS_ENV} google-cloud-filestore-pv
runApply ${KS_ENV} cert-manager
runApply ${KS_ENV} jupyterhub
runApply ${KS_ENV} ambassador
runApply ${KS_ENV} centraldashboard
runApply ${KS_ENV} tf-operator-job
runApply ${KS_ENV} spartakus
runApply ${KS_ENV} pytorch-operator

# TODO(jlewi): Is deleting the pod sufficient?
kubectl -n ${NAMESPACE} delete pods tf-hub-0

# Delete the envoy pods to force init container to 
# ensure IAP gets configured correctly and picks up any 
# config map changes.
kubectl -n ${NAMESPACE} delete pods -l service=envoy
