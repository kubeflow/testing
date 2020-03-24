# Cloud Connector

This directory contains configurations and scripts for using
[Config Connector](https://cloud.google.com/config-connector/) to declaratively
setup and manage Kubeflow Kubernetes clusters.

## Background

### Layout

All Config Connector managed projects live in the Google Cloud folder "kf-kcc".
The Kubernetes cluster with Config Connector lives in the "kf-kcc-admin"
project. Projects created via Config Connector exist in the "users" subfolder 
under the "kf-kcc-admin" project.

The current Google Cloud project and folder hierarchy is as follows:

 - kf-kcc (folder)
   - kf-kcc-admin (project)
     - users (folder)

### Setup

Currently, Config Connector is setup on a Kubernetes cluster named
"kubeflow-cloudconnector". Future Config Connector-managed clusters should be
created using the "kubeflow-cloudconnector" cluster against the "kf-kcc-admin"
namespace.

## Scripts

The following scripts assume the following:

1. The user has permissions and access to the 'kf-kcc-admin' Google Cloud
project
2. The user's gcloud config is set to the 'kf-kcc-admin' project
3. The user's kube config has the 'kf-kcc-admin' credentials and is using the
'kf-kcc-admin' context

`config_connector_setup.sh` sets up Config Connector using an existing GKE
cluster. This will set up service accounts, IAM, and secrets in the
'cnrm-system' namespace. The script requires a project ID as a parameter (in
this case, 'kf-kcc-admin'). You should also be in the context of the cluster you
want to install Config Connector on when running this script.

`community_cluster_setup.sh` sets up a GKE cluster for Kubeflow Community
projects with one master node and one worker node. It uses the namespace
"kf-kcc-admin", which is the name of the Google Cloud project. This script will
then apply the following YAML files:

- `containercluster.yaml`
- `iampolicy.yaml`
- `iamserviceaccount.yaml`
- `serviceaccount.yaml`
