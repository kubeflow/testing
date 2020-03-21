#!/usr/bin/env bash

# Sets up Config Connector -- gcloud must be setup correctly
# https://cloud.google.com/config-connector/docs/how-to/install-upgrade-uninstall

help()
{
  echo "Sets up Config Connector using gcloud"
  echo "Requires a project ID as the first parameter"
  echo
  echo "Usage: bash config_connector_setup.sh [project-id]"
}

if [[ $# -lt 1 ]] || [[ $1 == "-h" ]] || [[ $1 == "--help" ]]; then
  help
  exit 1
fi

PROJECT_ID="${1}"

echo -e "\e[31mBeginning setup...\e[0m"

if [[ ! $(gcloud iam service-accounts list | grep cnrm-system) ]]; then
  echo -e "\e[31mSetting up service accounts and IAM\e[0m"
  gcloud iam service-accounts create cnrm-system

  gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member serviceAccount:cnrm-system@${PROJECT_ID}.iam.gserviceaccount.com \
  --role roles/owner
fi

if [[ ! $(kubectl get ns cnrm-system) ]]; then
  echo -e "\e[31mCreating namespace and secret\e[0m"
  kubectl create namespace cnrm-system

  gcloud iam service-accounts keys create --iam-account \
  cnrm-system@${PROJECT_ID}.iam.gserviceaccount.com key.json

  kubectl create secret generic gcp-key --from-file key.json \
  --namespace cnrm-system

  rm key.json
fi

echo -e "\e[31mDownloading and installing config connector\e[0m"
gsutil cp gs://cnrm/latest/release-bundle.tar.gz release-bundle.tar.gz

tar -zxvf release-bundle.tar.gz && rm release-bundle.tar.gz

kubectl apply -f install-bundle-gcp-identity/
rm -rf install-bundle-*/ samples/

echo -e "\e[31mChecking for cnrm controller manager...\e[0m"
kubectl wait -n cnrm-system --for=condition=Initialized pod cnrm-controller-manager-0

echo -e "\e[31mSetup finished!\e[0m"
