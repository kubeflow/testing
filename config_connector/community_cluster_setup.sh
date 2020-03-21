#!/usr/bin/env bash

help()
{
  echo "Sets up the Kubeflow Community Cluster yaml"
  echo
  echo "Usage: bash community_cluster_setup.sh"
}

if [[ $1 == "-h" ]] || [[ $1 == "--help" ]]; then
  help
  exit 1
fi

namespace="kf-kcc-admin"

if [[ ! $(kubectl get ns ${namespace} 2> /dev/null) ]]; then
  echo -e "\e[31mCreating namespace 'kf-kcc-admin'\e[0m"
  kubectl create ns ${namespace}
fi

echo -e "\e[31mApplying YAML files\e[0m"
kubectl -n ${namespace} apply -f serviceaccount.yaml
kubectl -n ${namespace} apply -f iamserviceaccount.yaml
kubectl -n ${namespace} apply -f iampolicy.yaml
kubectl -n ${namespace} apply -f containercluster.yaml
kubectl -n ${namespace} apply -f containernodepool.yaml
