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

# This shell script is used to deploy kubeflow by kfctl

set -o errexit
set -o nounset
set -o pipefail

EKS_CLUSTER_NAME="${CLUSTER_NAME}"
EKS_NAMESPACE_NAME="${EKS_NAMESPACE}"

# Load kubeconfig
aws eks update-kubeconfig --name=$EKS_CLUSTER_NAME

cd /tmp

# Fetch v1.1-branch kfctl
wget https://github.com/PatrickXYS/kfctl/releases/download/test1/kfctl_v1.1.0-2-g08ee6e4_linux.tar.gz -O kfctl.tar.gz
tar -xvf kfctl.tar.gz

# Add kfctl to PATH, to make the kfctl binary easier to use.
export PATH=$PATH:"$PWD:kfctl"

echo "kfctl version: "
kfctl version

### Workaround to fix issue
## msg="Encountered error applying application bootstrap:  (kubeflow.error): Code 500 with message: Apply.Run
## : error when creating \"/tmp/kout927048001\": namespaces \"kubeflow-test-infra\" not found" filename="kustomize/kustomize.go:266"
kubectl create namespace $EKS_NAMESPACE_NAME
###

# Use the following kfctl configuration file for the AWS setup without authentication:
export CONFIG_URI="https://raw.githubusercontent.com/kubeflow/manifests/v1.1-branch/kfdef/kfctl_aws.v1.1.0.yaml"

# Set an environment variable for your AWS cluster name.
export AWS_CLUSTER_NAME=$EKS_CLUSTER_NAME

# Create the directory you want to store deployment, this has to be ${AWS_CLUSTER_NAME}
mkdir ${AWS_CLUSTER_NAME} && cd ${AWS_CLUSTER_NAME}

# Download your configuration files, so that you can customize the configuration before deploying Kubeflow.
wget -O kfctl_aws.yaml $CONFIG_URI

# Deploy Kubeflow
kfctl apply -V -f kfctl_aws.yaml
