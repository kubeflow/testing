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

if [ ! -d ~/secrets ]; then
	echo "~/secrets doesn't exist creating it to store client secrents"
	mkdir -p ~/secrets
fi

# We store the secret in a bucket to make it easy to share among the team.
# We rely on IAM to make this secure.
SECRET_FILE=client_secret_235037502967-9cpmvs4ljbiqb3ojtnhnhlkkd8d562rl.apps.googleusercontent.com.json
SECRET_BUCKET=kubeflow-dev-secrets

if [ ! -f ~/secrets/${SECRET_FILE} ]; then
	gsutil cp gs://${SECRET_BUCKET}/${SECRET_FILE} ~/secrets/${SECRET_FILE}
fi

LOCAL_FILE=~/secrets/${SECRET_FILE}
CLIENT_ID=`jq -r .web.client_id ${LOCAL_FILE}`
CLIENT_SECRET=`jq -r .web.client_secret ${LOCAL_FILE}`

SECRET_NAME="kubeflow-oauth"

set +e
kubectl get secret ${SECRET_NAME}
exists=$?
set -e

if [ "${exists}" -eq 0 ]; then
	kubectl -n ${NAMESPACE} delete secret ${SECRET_NAME}		
fi
kubectl -n ${NAMESPACE} create secret generic ${SECRET_NAME} --from-literal=CLIENT_ID=${CLIENT_ID} --from-literal=CLIENT_SECRET=${CLIENT_SECRET}

# Delete some confimaps so that will get recreated with the new config.
# TODO(jlewi): If we annotated the objects with a hash of the  config
# would ks apply automatically update them?
set +e
kubectl -n ${NAMESPACE} delete configmap envoy-config
kubectl -n ${NAMESPACE} delete configmap jupyterhub-config
kubectl -n ${NAMESPACE} delete configmap tf-job-operator-config
set -e

# TODO(jlewi): Do we need to delete the statefulset for 
# JupyterHub so that it will get updated?

ks apply default

# TODO(jlewi): Is deleting the pod sufficient?
kubectl -n ${NAMESPACE} delete pods tf-hub-0

# Delete the envoy pods to force init container to 
# ensure IAP gets configured correctly and picks up any 
# config map changes.
kubectl delete pods -l service=envoy
