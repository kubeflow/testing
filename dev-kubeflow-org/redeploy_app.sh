#!/bin/bash
#
# A helper script to redeploy the app.
#
# The script kicks some pods so that they get upgraded.

set -ex

NAMESPACE=kubeflow
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd ${DIR}

APP_NAME=ks-app

cd ${DIR}/${APP_NAME}

# Delete some confimaps so that will get recreated with the new config.
# TODO(jlewi): If we annotated the objects with a hash of the  config
# would ks apply automatically update them?
kubectl -n ${NAMESPACE} delete configmap envoy-config
kubectl -n ${NAMESPACE} delete configmap jupyterhub-config
kubectl -n ${NAMESPACE} delete configmap tf-job-operator-config

# TODO(jlewi): Do we need to delete the statefulset for 
# JupyterHub so that it will get updated?

ks apply default

# TODO(jlewi): Is deleting the pod sufficient?
kubectl -n ${NAMESPACE} delete pods tf-hub-0

# Delete the envoy pods to force init container to 
# ensure IAP gets configured correctly and picks up any 
# config map changes.
kubectl delete pods -l service=envoy
