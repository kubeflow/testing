#!/usr/bin/env bash

# Required Variables
export KUBEFLOW_REPO=${KUBEFLOW_REPO:-}
export PROJECT=${PROJECT:-}
export DEPLOYMENT_NAME=${DEPLOYMENT_NAME:-}
export CLIENT_ID=${CLIENT_ID:-}
export CLIENT_SECRET=${CLIENT_SECRET:-}
export K8S_NAMESPACE=${K8S_NAMESPACE:-kubeflow}

_SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Generate before using the folders
function generate_env() {
  # Override any existing KUBECONFIG to prevent side-effects.
  if [[ -f "${_SCRIPT_DIR}/dummykube" ]]; then
    cp -f ~/.kube/config ~/.kube/config.bak
    cp -f "${_SCRIPT_DIR}/dummykube" ~/.kube/config
  fi

  ${KUBEFLOW_REPO}/scripts/kfctl.sh init ${DEPLOYMENT_NAME} --platform gcp --project ${PROJECT}
}


function generate_and_apply() {
  pushd ${DEPLOYMENT_NAME}

  ${KUBEFLOW_REPO}/scripts/kfctl.sh generate all
  ${KUBEFLOW_REPO}/scripts/kfctl.sh apply all

  popd

  kubectl config unset clusters.localhost
  kubectl config unset contexts.localhost
  kubectl config unset users.localhost
}

function delete() {
  pushd ${DEPLOYMENT_NAME}

  ${KUBEFLOW_REPO}/scripts/kfctl.sh delete all

  popd

  # rm -r ${DEPLOYMENT_NAME}
}

function upgrade_ks() {
  pushd ${DEPLOYMENT_NAME}

  rm -r ks_app/

  generate_and_apply

  popd

  # rm -r ${DEPLOYMENT_NAME}
}


if [[ "$1" = "generate_env" ]]; then
  generate_env
elif [[ "$1" = "generate_and_apply" ]]; then
  generate_and_apply
elif [[ "$1" = "delete" ]]; then
  delete
elif [[ "$1" = "upgrade_ks" ]]; then
  upgrade_ks
fi
