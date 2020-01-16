<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Kubeflow CI with tektoncd pipelines](#kubeflow-ci-with-tektoncd-pipelines)
  - [Use Cases](#use-cases)
  - [Background information on TektonCD pipelineruns, pipelines and tasks](#background-information-on-tektoncd-pipelineruns-pipelines-and-tasks)
  - [Parameterization](#parameterization)
  - [Secrets](#secrets)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Kubeflow CD with tektoncd pipelines

This directory contains Tekton pipelines intended to rebuild Kubeflow docker images 
and open PRs to update Kubeflow kustomize manifests to use the newly built images.

### How it works

* pipelines/base/pipeline.yaml defines a reusable pipeline to:

  1. Build a container image
  1. Create a PR to update the Kubeflow manifests to use the newly built image

* To launch a pipeline to build a specific application at a specific commit you create an instance of a pipeline run
  that uses this pipeline

  * runs/profile_controller_v1795828.yaml provides an example pipeline run to build and update the profile controller image

  * [pipeline resources](https://github.com/tektoncd/pipeline/blob/master/docs/resources.md) and [pipeline parameters](https://github.com/tektoncd/pipeline/blob/master/docs/pipelines.md#parameters) to specify what application to build and the image to create

    * [Git Resources](https://github.com/tektoncd/pipeline/blob/master/docs/resources.md#git-resource) are used to define

      * The repo and commit containing the source code to build the image from
      * The repo containing the manifests to update
      * The repo and commit containing the tools used for CI/CD

    * [Image Resource](https://github.com/tektoncd/pipeline/blob/master/docs/resources.md#image-resource) is used to define
      the docker image to use

    * Parameters are used to define various values specific to each application such as the relative paths of the Docker file
      in the source repository

 * The kubeflow-bot GitHub account is used to create the PRs

 * Continuous building is achieved by running `update_launcher.py` in a Kubernetes deployment

   * This script periodically fetches the latest code in `kubeflow/testing` to pick up any changes
     to the code or config

   * It then launches `update_kf_apps.py` to create Tekton PipelineRuns for any applications that
     need to be updated.

### Adding Applications to continuous delivery

Here are instructions for adding an application for continous delivery

* You should add an entry to [applications.yaml](applications.yaml) for that application

* Set the parameters as needed for that application

### Defining a New Version/Release For Applications

* The versions in [applications.yaml](applications.yaml) specify the different
  releases e.g. master, v0.X, v0.Y, etc... at which to build the applications

* For every version we define

  * **tag** This is a label like "vmaster" or "v0.X.1" that will be used to tag the images
  * The source repos and corresponding branch from which to build the images

    * Each time the create-runs script is run it will create a pipeline run that uses the tip
      of that branch for that source

  * A repo for kubeflow manifests that specifies the branch of the kustomize package to update


### Run a pipeline 

To update a specific application

1. Connect to the Kubeflow releasing cluster

   * **project**: **kf-releasing**
   * **cluster**: **kf-releasing-0-6-2**
   * **namespace**: **kf-releasing**

1. Create a PipelineRun file

   * You can use one of the runs in runs/ as a baseline
   * Set the Tekton PipelineRun parameters and resources as needed to build your
     application at the desired commit 

1. Generate the pipeline runs for the latest commits
    
   ```
   KUBEFLOW_TESTING=<Path where kubeflow/testing is checked out>
   OUTPUT_DIR=<Directory to write the PipelineRuns YAML files>
   SRC_DIR=<Directory where source repos should be checked out>
   CONFIG=${KUBEFLOW_TESTING}/apps-cd/applications.yaml
   TEMPLATE=${KUBEFLOW_TESTING}/apps-cd/runs/app-pipeline.template.yaml 

   cd ${KUBEFLOW_TESTING}/py
   python3 -m kubeflow.testing.cd.update_kf_apps create-runs \
      --config=${CONFIG} \
      --output_dir=${OUTPUT_DIR} \
      --src_dir=${SRC_DIR} \ 
      --template=${TEMPLATE}

   ```

   * This will create a YAML file for every (application, version) combination

1. Submit PipelineRun's to the release cluster

   ```
   kubectl create -f ${OUTPUT_DIR}
   ```

### Setting up a cluster to run the pipelines

The kustomize manifests are currently written so as to run in a Kubeflow releasing cluster.

The current release cluster is

* **project**: **kf-releasing**
* **cluster**: **kf-releasing-0-6-2**
* **namespace**: **kf-releasing**

This is a Kubeflow cluster (v0.6.2) and we rely on that to configure certain things like the secrets and service accounts.

1. Follow [Tektons' instructions](https://github.com/tektoncd/pipeline/blob/master/docs/auth.md#ssh-authentication-git) for
   creating a secret containing ssh credentials for use with GitHub

   * We are currently using the secret named **kubeflow-bot-github-ssh**


1. Ensure the GCP service account used with Kaniko has storage admin permissions for the project
   where the images are pushed.

   * most likely **gcr.io/kubeflow-images-public**

1. Create a secret named **github-token** containing a github token to be used by the hub CLI to create PRs.

1. Create the Tekton resources

   ```
   kustomize build pipelines/base/ | kubectl apply -f -
   ```

## Developer Guide

You can use skaffold to build a docker image and auto update the deployment running `update_launcher.py`

1. Run skaffold

   ```
   skaffold dev -v info --cleanup=false --trigger=polling
   ```

1. During development you can take advantage of skaffold's continuous file sync mode to update
   the code `update_launcher.py` without rebuilding the docker image or updating the deployment

   * To take advantage of this modify `base/deployment.yaml` and uncomment the lines

     ```
     - python
     - run_with_auto_restart.py
     - --dir=/app
     ```

   * This runs update_launcher.py in a subprocess and restarts it everytime it detects a change in the file

## Deploying Or Updating the Continuous run

Use skaffold 

```
skaffold run --cleanup=False
```

* TODO(jlewi): Do we need to set cleanup to false.

## References

1. [Design Doc](https://docs.google.com/document/d/1AwYVznJ0F5ZwVrClATff2wXUKE-OnygIlwY1NRTv-2I/edit#heading=h.9g4gb5dvlquq)