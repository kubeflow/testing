#!/usr/bin/env bash

if [[ ! $(kubectl get ns kf-community) ]]; then
  echo "Creating namespace 'kf-community'"
  kubectl create ns kf-community
fi

kubectl -n kf-community apply -f containercluster.yaml
kubectl -n kf-community apply -f serviceaccount.yaml
kubectl -n kf-community apply -f iamserviceaccount.yaml
kubectl -n kf-community apply -f iampolicy.yaml
