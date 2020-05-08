# Kubeflow Auto Deploy Infrastructure

Kubeflow auto deploy is reponsible for automatically deploying
Kubeflow instances from the latest code on a branch.

This directory contains the Kubernetes manifests and Docker images
for auto-deploying Kubeflow instances from the latest code on a branch.

The python code is located in [py/kubeflow/testing/auto_deploy](https://github.com/kubeflow/testing/tree/master/py/kubeflow/testing/auto_deploy).

## Quick Links

* [Auto Deployments Dashboard](https://kf-ci-v1.endpoints.kubeflow-ci.cloud.goog/auto_deploy/)
* [Tekton Dashboard for deploy-gcp-blueprint runs](https://kf-ci-v1.endpoints.kubeflow-ci.cloud.goog/tekton/#/namespaces/auto-deploy/pipelineruns?labelSelector=tekton.dev%2Fpipeline%3Ddeploy-gcp-blueprint)
* [Stack Driver Logs For Reconciler](https://console.cloud.google.com/logs/viewer?project=kubeflow-ci&folder&organizationId&minLogLevel=0&expandAll=false&&customFacets=&limitCustomFacetWidth=true&interval=PT1H&resource=k8s_container%2Fcluster_name%2Fkubeflow-testing%2Fnamespace_name%2Ftest-pods&advancedFilter=resource.type%3D%22k8s_container%22%0Aresource.labels.cluster_name%3D%22kf-ci-v1%22%0Aresource.labels.container_name%20%3D%20%22blueprints-reconciler%22%0Alabels.%22k8s-pod%2Fapp%22%20%3D%20%22auto-deploy%22%0A)
* [Stack Driver Logs For Flask App](https://console.cloud.google.com/logs/viewer?project=kubeflow-ci&folder&organizationId&minLogLevel=0&expandAll=false&&customFacets=&limitCustomFacetWidth=true&interval=PT1H&resource=k8s_container%2Fcluster_name%2Fkubeflow-testing%2Fnamespace_name%2Ftest-pods&advancedFilter=resource.type%3D%22k8s_container%22%0Aresource.labels.cluster_name%3D%22kf-ci-v1%22%0Aresource.labels.container_name%20%3D%20%22server%22%0Alabels.%22k8s-pod%2Fapp%22%20%3D%20%22auto-deploy%22%0A)

## How it works

There are three key pieces:

1. [blueprint_reconciler.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/auto_deploy/blueprint_reconciler.py)

   * The reconciler periodically checks whether its necessary to create a new instance of Kubeflow

   * The reconciler checks whether there have been changes committed since the most recent auto deployments
       were created

   * If a newer version of Kubeflow needs to be created; the reconciler will try to deploy it immediately if
     various conditions are met

     * The reconciler implements a rate limiting queue to prevent too many instances of Kubeflow being
       created simultaneously and eating up all the quota

   * The reconciler will fire off Tekton Pipelines to create a Kubeflow deployment as needed

     * The PipleineRun's are defined in [kubeflow/testing/test-infra/auto-deploy/manifest/config](https://github.com/kubeflow/testing/tree/master/test-infra/auto-deploy/manifest/config)

       * These are uploaded via a configmap to the reconciler.

1. [reconciler.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/auto_deploy/reconciler.py)

   * This is deprecated its replaced by blueprint_reconciler.py

   * The reconciler periodically checks whether its necessary to create a new instance of Kubeflow

     * The reconciler checks whether there have been changes committed since the most recent auto deployments
       were created

   * If a newer version of Kubeflow needs to be created; the reconciler will try to deploy it immediately if
     various conditions are met

     * The reconciler implements a rate limiting queue to prevent too many instances of Kubeflow being
       created simultaneously and eating up all the quota

   * The reconciler will fire off Kubernetes Jobs to create a Kubeflow deployment as needed

     * [deploy-kubeflow.yaml](https://github.com/kubeflow/testing/blob/master/test-infra/auto-deploy/manifest/config/deploy-kubeflow.yaml) provides a template for these K8s jobs

       * The template gets modified by the reconciler.

     * [deployments.yaml](https://github.com/kubeflow/testing/blob/master/test-infra/auto-deploy/manifest/config/deployments.yaml)  configures how to deploy Kubeflow deployments

       * each version points to a KFDef and version of kfctl to use to deploy Kubeflow

          
1. A [flask app](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/auto_deploy/server.py)
   provides a simple server for getting information about the latest auto deployments

   * The flask app is served at [https://kf-ci-v1.endpoints.kubeflow-ci.cloud.goog/auto_deploy/](https://kf-ci-v1.endpoints.kubeflow-ci.cloud.goog/auto_deploy/)

## What's it for

The primary purpose of the auto deployed clusters is to provide up to date clusters for manual and automatic tests.

For example, test in kubeflow/examples should be configured to select an auto deployed cluster and then run against that.  


## How to deploy it

The reconciler is currently running in 

* **project**: kubeflow-ci
* **cluster**: kf-ci-v1
* **namespace**: auto-deploy

The auto-deployer can be updated using skaffold

```
skaffold run -v info 
```

* You must select the appropriate skaffold profile; e.g. by setting your context to match the context listed in skaffold.yaml