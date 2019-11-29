# Cloud Connector

This directory contains configurations and scripts for using
[Config Connector](https://cloud.google.com/config-connector/) to setup
Kubernetes clusters.

## Setup

Run `bash config_connector_setup.sh [project-id]` to setup Config Connector on
an existing GKE cluster. This will setup service accounts, IAM, and secrets in
the 'cnrm-system' namespace. Right now we are using "kf-kcc" (folder) and
"kf-kcc-admin" (project).

Run `bash community_cluster_setup.sh` to setup a GKE cluster for Kubeflow
Community projects in a namespace called "kf-community" using an existing
cluster with Config Connector. This script will apply the following yaml files:
`containercluster.yaml`, `serviceaccount.yaml`, `iamserviceaccount.yaml`,
`iampolicy.yaml`.
