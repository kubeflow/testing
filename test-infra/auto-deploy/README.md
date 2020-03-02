# Kubeflow Auto Deploy Infrastructure

Kubeflow auto deploy is reponsible for automatically deploying
Kubeflow instances from the latest code on a branch.

This directory contains the Kubernetes manifests and Docker images
for auto-deploying Kubeflow instances from the latest code on a branch.

The python code is located in [py/kubeflow/testing/auto_deploy](https://github.com/kubeflow/testing/tree/master/py/kubeflow/testing/auto_deploy).

## How it works

There are two key pieces:

1. [reconciler.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/auto_deploy/reconciler.py)

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