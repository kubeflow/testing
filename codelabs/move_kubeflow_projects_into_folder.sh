#!/bin/bash
# 
# A script to move all the Kubeflow projects into the kubeflow folder
#
# To use the script
#  1. set PROJECT_BASE to base name of the project names
#  2. Update for loop counter
set -x

# The name of the organization
ORG_NAME=gcplab.me

# The name of the folder
FOLDER=kubeflow-codelabs

FOLDER_ID=$(gcloud resource-manager folders list --organization=${ORG_ID} --filter=display_name=${FOLDER} --format='value(ID)')

# Base name for the project
BASE_PROJECT=kf-test

if [ -z ${FOLDER_ID} ]; then
	echo Could not get ID of folder ${FOLDER} in organization ${ORG_NAME}
	exit 1
fi

for COUNTER in `seq 8002 8100`; do
   gcloud beta projects move ${BASE_PROJECT}-${COUNTER} --folder ${FOLDER_ID}
done