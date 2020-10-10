#!/bin/bash

# Copyright 2018 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This shell script is used to check if all deployments are RUNNING

set -o errexit
set -o nounset
set -o pipefail

EKS_CLUSTER_NAME="${CLUSTER_NAME}"

aws eks update-kubeconfig --name=$EKS_CLUSTER_NAME

echo "Start Fetching Ingress IP Address"

# Retry 10 times w/ 30 seconds interval
retry_times=0
retry_limit=10
while [ "$retry_times" -lt "$retry_limit" ]
do
  echo "See if we can fetch ingress"
  ingress_ip=$(kubectl get ingress istio-ingress -n istio-system  -o json | jq -r '.status.loadBalancer.ingress[0].hostname')
  if [ ${#ingress_ip} -eq 0 ] ;
  then
    sleep 30
    echo "Retrying Fetching Ingress IP Address"
  else
    echo "The Kubeflow Deployment succeeded"
    exit 0
  fi

  retry_times=$((retry_times+1))
done

echo "Kubeflow Deployment Status: ERROR"
exit 64