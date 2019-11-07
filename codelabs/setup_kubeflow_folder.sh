#!/bin/bash
#
# This is a script intended to be run onetime by the gcplab.me 
# team to create a folder for the kubeflow codelab projects.
set -x

# The name of the organization
ORG_NAME=gcplab.me

# The name of the folder
FOLDER=kubeflow-codelabs

# The group to grant ownership of the folder
GROUP=kubeflow-codelab-folder-admins@google.com

set -e
ORG_ID=$(gcloud organizations list --filter=display_name=${ORG_NAME} --format='value(ID)')
set +e

FOLDER_ID=$(gcloud resource-manager folders list --organization=${ORG_ID} --filter=display_name=${FOLDER} --format='value(ID)')

if [ -z ${FOLDER_ID} ]; then
	echo ${FOLDER} does not exist creating it
	set -e
	gcloud alpha resource-manager folders create \
	   --display-name=${FOLDER} \
	   --organization=${ORG_ID}
	set +e	
fi

FOLDER_ID=$(gcloud resource-manager folders list --organization=${ORG_ID} --filter=display_name=${FOLDER} --format='value(ID)')

if [ -z ${FOLDER_ID} ]; then
	echo Could not get ID of folder ${FOLDER} in organization ${ORG_NAME}
	exit 1
fi

roles=( "roles/resourcemanager.folderAdmin" "roles/resourcemanager.projectIamAdmin" )

for r in "${roles[@]}"
do
	gcloud alpha resource-manager folders \
	  add-iam-policy-binding ${FOLDER_ID} \
	  --member=group:${GROUP} \
	  --role=${r}
done