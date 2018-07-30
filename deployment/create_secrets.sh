#!/bin/bash
#
# A helper script to create the secrets in the cluster.
set -ex

NAMESPACE=kubeflow-oauth

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
kubectl -n ${NAMESPACE} create secret generic ${SECRET_NAME} \
	--from-literal=CLIENT_ID=${CLIENT_ID} --from-literal=CLIENT_SECRET=${CLIENT_SECRET}
