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

1. Run it
    
   ```
   kubectl create -f ${PIPELINERUN_FILE}
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

## References

1. [Design Doc](https://docs.google.com/document/d/1AwYVznJ0F5ZwVrClATff2wXUKE-OnygIlwY1NRTv-2I/edit#heading=h.9g4gb5dvlquq)