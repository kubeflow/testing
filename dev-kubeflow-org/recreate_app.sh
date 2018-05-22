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

# Checkout versions of the code that shouldn't be overwritten
raw=`git remote`
readarray -t remotes <<< "$raw"

repo_name=''
for r in "${remotes[@]}"
do
   url=`git remote get-url ${r}`
   if [ ${url} = 'git@github.com:kubeflow/testing.git' ]; then
   	  repo_name=${r}
   fi
done

if [ -z "$repo_name" ]; then
    echo "Could not find remote repository pointing at git@github.com:kubeflow/testing.git"
fi


# Install Kubeflow components
ks registry add kubeflow github.com/kubeflow/kubeflow/tree/${VERSION}/kubeflow

ks pkg install kubeflow/core@${VERSION}
ks pkg install kubeflow/tf-serving@${VERSION}
ks pkg install kubeflow/tf-job@${VERSION}
ks pkg install kubeflow/seldon@${VERSION}

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


# Checkout files that are manually created from the master branch.
# Since we restore params.libsonnet we restore all values of params
files=( "issue-summarization.jsonnet" "issue-summarization-ui.jsonnet" "seldon.jsonnet" "params.libsonnet")
for f in "${files[@]}"
do
git  checkout ${repo_name} components/${f}
done


# TODO(jlewi): We should run autoformat.
