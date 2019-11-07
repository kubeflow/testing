#!/bin/bash
# 
# A script to move all the Kubeflow projects into the kubeflow folder
#
# Usage:
#
# BASE_PROJECT=someproject SEQ_START=100 SEQ_END=200 ./codelabs/move_kubeflow_projects_into_folder.sh 
set -x

# The name of the organization
ORG_NAME=${ORG_NAME:-gcplab.me}

# The name of the folder
FOLDER=${FOLDER:-kubeflow-codelabs}

# Base name for the project
BASE_PROJECT=${BASE_PROJECT:-kf-test}
SEQ_START=${SEQ_START:-9990}
SEQ_END=${SEQ_END:-9999}

ORG_ID=$(gcloud organizations list --filter=display_name=${ORG_NAME} --format='value(ID)')
FOLDER_ID=$(gcloud resource-manager folders list --organization=${ORG_ID} --filter=display_name=${FOLDER} --format='value(ID)')

if [ -z ${FOLDER_ID} ]; then
	echo Could not get ID of folder ${FOLDER} in organization ${ORG_NAME}
	exit 1
fi

for COUNTER in `seq ${SEQ_START} ${SEQ_END}`; do
   gcloud beta projects move ${BASE_PROJECT}-${COUNTER} --folder ${FOLDER_ID}
done