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
VERSION=v0.1.0-rc.4

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd ${DIR}

APP_NAME=ks-app


if [ -d ${DIR}/${APP_NAME} ]; then
	# TODO(jlewi): Maybe we should prompt to ask if we want to delete?	
	echo "Directory ${DIR}/${APP_NAME} exists"
	echo "Do you want to delete ${DIR}/${APP_NAME} y/n[n]:"
	read response

	if [ "${response}"=="y" ]; then
		rm -r ${DIR}/${APP_NAME}
	else
		"Aborting"
		exit 1
	fi	
fi

ks init ${APP_NAME}
cd ${APP_NAME}
ks env set default --namespace ${NAMESPACE}

# Install Kubeflow components
ks registry add kubeflow github.com/kubeflow/kubeflow/tree/${VERSION}/kubeflow

ks pkg install kubeflow/core@${VERSION}
ks pkg install kubeflow/tf-serving@${VERSION}
ks pkg install kubeflow/tf-job@${VERSION}

# Create templates for core components
ks generate kubeflow-core kubeflow-core

# Setup ingress
ACCOUNT=google-kubeflow-team@google.com
CLIENT_ID="235037502967-9cpmvs4ljbiqb3ojtnhnhlkkd8d562rl.apps.googleusercontent.com"
CLIENT_SECRET="eNyoA-ZtqC_HSSx95mGRPLR3"
FQDN=dev.kubeflow.org
IP_NAME="kubeflow-tf-hub"
ks generate cert-manager cert-manager --acmeEmail=${ACCOUNT}
ks generate iap-ingress iap-ingress --namespace=${NAMESPACE} \
	--ipName=${IP_NAME} \
	--hostname="${FQDN}" \
	--oauthSecretName="kubeflow-oauth"

ks param set kubeflow-core jupyterHubAuthenticator iap

# Enable collection of anonymous usage metrics
# Skip this step if you don't want to enable collection.
#
# We use the same usage id on redeployments so we won't conflate
# redeployments with unique clusters.
USAGE_ID=f85740a3-5f60-4146-91b6-2ab7089cf01c
ks param set kubeflow-core reportUsage true
ks param set kubeflow-core usageId ${USAGE_ID}
