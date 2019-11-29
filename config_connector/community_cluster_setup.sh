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

if [[ ! $(kubectl get ns kf-community) ]]; then
  echo "Creating namespace 'kf-community'"
  kubectl create ns kf-community
fi

kubectl -n kf-community apply -f containercluster.yaml
kubectl -n kf-community apply -f serviceaccount.yaml
kubectl -n kf-community apply -f iamserviceaccount.yaml
kubectl -n kf-community apply -f iampolicy.yaml
