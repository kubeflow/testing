#!/usr/bin/env bash

# Sets up Config Connector -- gcloud must be setup correctly
# https://cloud.google.com/config-connector/docs/how-to/install-upgrade-uninstall

help()
{
  echo "Sets up Config Connector using gcloud"
  echo "Requires a project ID as the first parameter"
  echo
  echo "Usage: bash ccsetup.sh [project-id]"
}

if [[ $# -lt 1 ]] || [[ $1 == "-h" ]]; then
  help
  exit 1
fi

PROJECT_ID="${1}"

echo "Setting up service accounts and IAM"
if [[ ! $(gcloud iam service-accounts list | grep cnrm-system) ]]; then
  gcloud iam service-accounts create cnrm-system

  gcloud projects add-iam-policy-binding ${PROJECT_ID} \
--member serviceAccount:cnrm-system@${PROJECT_ID}.iam.gserviceaccount.com \
--role roles/owner
fi

gcloud iam service-accounts keys create --iam-account \
cnrm-system@${PROJECT_ID}.iam.gserviceaccount.com key.json

echo "Creating namespace and secret"
if [[ ! $(kubectl get ns cnrm-system) ]]; then
  kubectl create namespace cnrm-system
  kubectl create secret generic gcp-key --from-file key.json --namespace cnrm-system
  rm key.json
fi

echo "Downloading and installing config connector"
curl -X GET -sLO \
-H "Authorization: Bearer $(gcloud auth print-access-token)" \
--location-trusted \
https://us-central1-cnrm-eap.cloudfunctions.net/download/latest/infra/install-bundle.tar.gz

tar zxvf install-bundle.tar.gz && rm install-bundle.tar.gz

kubectl apply -f install-bundle/

echo "Checking for cnrm controller manager..."
kubectl wait -n cnrm-system \
--for=condition=Initialized pod \
cnrm-controller-manager-0
