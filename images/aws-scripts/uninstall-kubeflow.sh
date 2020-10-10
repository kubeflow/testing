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

# This shell script is used to uninstall kubeflow by kfctl

set -o errexit
set -o nounset
set -o pipefail

EKS_CLUSTER_NAME="${CLUSTER_NAME}"
EKS_NAMESPACE_NAME="${EKS_NAMESPACE}"

# Load kubeconfig
aws eks update-kubeconfig --name=$EKS_CLUSTER_NAME

# Add kfctl to PATH, to make the kfctl binary easier to use.
export PATH=$PATH:"$PWD:kfctl"

echo "kfctl version: "
kfctl version

# Cd directory ${EKS_CLUSTER_NAME}
cd ${EKS_CLUSTER_NAME}

# Print YAML file
cat kfctl_aws.yaml

# Uninstall Kubeflow
kfctl delete -V -f kfctl_aws.yaml