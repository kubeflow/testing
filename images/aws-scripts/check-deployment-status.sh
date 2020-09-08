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

EKS_CLUSTER_NAME="${EKS_CLUSTER}"

# Allow 5 minutes to wait for kubeflow deployment to be ready
sleep 5m

aws eks update-kubeconfig --name=$EKS_CLUSTER_NAME

ingress_ip=$(kubectl get ingress istio-ingress -n istio-system  -o json | jq '.status.loadBalancer.ingress' | grep aws)

if [ ${#ingress_ip} -eq 0 ] ;then echo "ERROR" >&2 & exit 64; fi

echo "The Kubeflow Deployment succeeded"
