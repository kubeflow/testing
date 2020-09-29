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

# This shell script is used to build an EKS cluster from our argo workflow

set -o errexit
set -o nounset
set -o pipefail

EKS_CLUSTER_NAME="${CLUSTER_NAME}"

# Create EKS Cluster
# TODO (PatrickXYS): Need to determine which NG template we need
eksctl create cluster \
--name $EKS_CLUSTER_NAME \
--version ${EKS_CLUSTER_VERSION:-"1.17"} \
--region ${AWS_REGION:-"us-west-2"} \
--nodegroup-name linux-nodes \
--node-type ${EKS_NODE_TYPE:-"m5.xlarge"} \
--nodes ${DESIRED_NODE:-"2"} \
--nodes-min ${MIN_NODE:-"1"} \
--nodes-max ${MAX_NODE:-"4"} \
--managed
