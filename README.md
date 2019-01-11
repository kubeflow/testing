<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Test Infrastructure](#test-infrastructure)
  - [Anatomy of our Tests](#anatomy-of-our-tests)
  - [Accessing The Argo UI](#accessing-the-argo-ui)
  - [Working with the test infrastructure](#working-with-the-test-infrastructure)
  - [Logs](#logs)
    - [Prow](#prow)
    - [Argo UI](#argo-ui)
    - [Stackdriver logs](#stackdriver-logs)
  - [Debugging Failed Tests](#debugging-failed-tests)
    - [No results show up in Gubernator](#no-results-show-up-in-gubernator)
    - [No Logs in Argo UI or Pod Id missing in Argo Logs](#no-logs-in-argo-ui-or-pod-id-missing-in-argo-logs)
    - [Debugging Failed Deployments](#debugging-failed-deployments)
  - [Testing Changes to the ProwJobs](#testing-changes-to-the-prowjobs)
  - [Cleaning up leaked resources](#cleaning-up-leaked-resources)
  - [Integration with K8s Prow Infrastructure.](#integration-with-k8s-prow-infrastructure)
  - [Setting up Kubeflow Test Infrastructure](#setting-up-kubeflow-test-infrastructure)
    - [Create a static ip for the Argo UI](#create-a-static-ip-for-the-argo-ui)
    - [Enable GCP APIs](#enable-gcp-apis)
    - [Create a GCP service account](#create-a-gcp-service-account)
    - [Create a GitHub Token](#create-a-github-token)
    - [Deploy NFS](#deploy-nfs)
    - [Create K8s Resources for Testing](#create-k8s-resources-for-testing)
      - [Troubleshooting](#troubleshooting)
  - [Setting up a Kubeflow Repository to Use Prow <a id="prow-setup"></a>](#setting-up-a-kubeflow-repository-to-use-prow-a-idprow-setupa)
  - [Writing An Argo Workflow For An E2E Test](#writing-an-argo-workflow-for-an-e2e-test)
    - [Adding an E2E test to a repository](#adding-an-e2e-test-to-a-repository)
    - [Prow Variables](#prow-variables)
    - [Argo Spec](#argo-spec)
    - [Creating K8s resources in tests.](#creating-k8s-resources-in-tests)
    - [NFS Directory](#nfs-directory)
    - [Step Image](#step-image)
    - [Checking out code](#checking-out-code)
    - [Building Docker Images](#building-docker-images)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Test Infrastructure

This directory contains the Kubeflow test Infrastructure.

We use [Prow](https://github.com/kubernetes/test-infra/tree/master/prow),
K8s' continuous integration tool.

  * Prow is a set of binaries that run on Kubernetes and respond to
GitHub events.

We use Prow to run:

  * Presubmit jobs
  * Postsubmit jobs
  * Periodic tests

Here's how it works

  * Prow is used to trigger E2E tests
  * The E2E test will launch an Argo workflow that describes the tests to run
  * Each step in the Argo workflow will be a binary invoked inside a container
  * The Argo workflow will use an NFS volume to attach a shared POSIX compliant filesystem to each step in the
    workflow.
  * Each step in the pipeline can write outputs and junit.xml files to a test directory in the volume
  * A final step in the Argo pipeline will upload the outputs to GCS so they are available in gubernator

Quick Links

  * [Argo UI](http://testing-argo.kubeflow.org/)
  * [Test Grid](https://k8s-testgrid.appspot.com/sig-big-data)
  * [Prow jobs for kubeflow/kubeflow](https://prow.k8s.io/?repo=kubeflow%2Fkubeflow)

## Anatomy of our Tests

* Our prow jobs are defined [here](https://github.com/kubernetes/test-infra/tree/master/config/jobs/kubeflow)
* Each prow job defines a K8s PodSpec indicating a command to run
* Our prow jobs use [run_e2e_workflow.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/run_e2e_workflow.py)
  to trigger an Argo workflow that checks out our code and runs our tests.
* Our tests are structured as Argo workflows so that we can easily perform steps in parallel.
* The Argo workflow is defined in the repository being tested
   * We always use the worfklow at the commit being tested
* [checkout.sh](https://github.com/kubeflow/testing/blob/master/images/checkout.sh) is used to checkout the code being tested
   * This also checks out [kubeflow/testing](https://github.com/kubeflow/testing/) so that all repositories can
     rely on it for shared tools.

## Accessing The Argo UI

The UI is publicly available at http://testing-argo.kubeflow.org/

## Working with the test infrastructure

The tests store the results of tests in a shared NFS filesystem. To inspect the results you can mount the NFS volume.

To make this easy, We run a stateful set in our test cluster that mounts the same volumes as our Argo workers. Furthermore, this stateful set
is using an environment (GCP credentials, docker image, etc...) that mimics our Argo workers. You can
ssh into this stateful set in order to get access to the NFS volume.

```
kubectl exec -it debug-worker-0 /bin/bash
```

This can be very useful for reproducing test failures.

## Logs

Logs from the E2E tests are available in a number of places and can be used to troubleshoot test failures.

### Prow

These should be publicly accessible.

The logs from each step are copied to GCS and made available through gubernator. The K8s-ci robot should post
a link to the gubernator UI in the PR. You can also find them as follows

1. Open up the prow jobs dashboard e.g. [for kubeflow/kubeflow](https://prow.k8s.io/?repo=kubeflow%2Fkubeflow)
1. Find your job
1. Click on the link under job; this goes to the Gubernator dashboard
1. Click on artifacts
1. Navigate to artifacts/logs

If these logs aren't available it could indicate a problem running the step that uploads the artifacts to GCS for gubernator. In this
case you can use one of the alternative methods listed below.

### Argo UI

The argo UI is publicly accessible at http://testing-argo.kubeflow.org/timeline.

1. Find and click on the workflow corresponding to your pre/post/periodic job
1. Select the workflow tab
1. From here you can select a specific step and then see the logs for that step

### Stackdriver logs

Since we run our E2E tests on GKE, all logs are persisted in [Stackdriver logging](https://console.cloud.google.com/logs/viewer?project=kubeflow-ci&resource=container%2Fcluster_name%2Fkubeflow-testing&advancedFilter=resource.type%3D"container"%0Aresource.labels.cluster_name%3D"kubeflow-testing"%0A).

Viewer access to Stackdriver logs is available by joining one of the following groups

  * ci-viewer@kubeflow.org
  * ci-team@kubeflow.org

If you know the pod id corresponding to the step of interest then you can use the following Stackdriver filter

```
resource.type="container"
resource.labels.cluster_name="kubeflow-testing"
resource.labels.container_name = "main"
resource.labels.pod_id=${POD_ID}
```

The ${POD_ID} is of the form

```
${WORKFLOW_ID}-${RANDOM_ID}
```

## Debugging Failed Tests

### No results show up in Gubernator

If no results show up in Gubernator this means the prow job didn't get far enough to upload any results/logs to GCS.

To debug this you need the pod logs. You can access the pod logs via the build log link for your job in the [prow jobs UI](https://prow.k8s.io/)

  * Pod logs are ephmeral so you need to check shortly after your job runs.

The pod logs are available in StackDriver but only the Google Kubeflow Team has access
  * Prow runs on a cluster owned by the K8s team not Kubeflow
  * This policy is determined by K8s not Kubeflow
  * This could potentially be fixed by using our own prow build cluster [issue#32](https://github.com/kubeflow/testing/issues/32)

To access the stackdriver logs 
  
  * Open stackdriver for project [k8s-prow-builds](https://console.cloud.google.com/logs/viewer?organizationId=433637338589&project=k8s-prow-builds&folder&minLogLevel=0&expandAll=false&timestamp=2018-05-22T17:09:26.625000000Z&customFacets&limitCustomFacetWidth=true&dateRangeStart=2018-05-22T11:09:27.032Z&dateRangeEnd=2018-05-22T17:09:27.032Z&interval=PT6H&resource=gce_firewall_rule&scrollTimestamp=2018-05-22T15:40:23.000000000Z&advancedFilter=resource.type%3D"container"%0Aresource.labels.pod_id%3D"15f5a424-5dd6-11e8-826c-0a580a6c0117"%0A)
  * Get the pod ID by clicking on the build log in the [prow jobs UI](https://prow.k8s.io/)
  * Filter the logs using 

  ```
  resource.type="container"
  resource.labels.pod_id=${POD_ID}
  ```

  * For example, if the TF serving workflow failed, filter the logs using
  ```
  resource.type="container"
  resource.labels.cluster_name="kubeflow-testing"
  labels."container.googleapi.com/namespace_name"=WORKFLOW_NAME
  resource.labels.container_name="mnist-cpu"
  ```

### No Logs in Argo UI or Pod Id missing in Argo Logs

An Argo workflow fails and you click on the failed step in the Argo UI to get the logs
and you see the error

```
failed to get container status {"docker" "b84b751b0102b5658080a520c9a5c2655855960c4695cf557c0c1e45999f7429"}: rpc error: code = Unknown desc = Error: No such container: b84b751b0102b56580
80a520c9a5c2655855960c4695cf557c0c1e45999f7429
```

This error is a red herring; it means the pod is probably gone so Argo couldn't get the logs.

The logs should be in StackDriver but to get them we need to identify the pod

1. Get the workflow using kubectl

   ```
   kubectl get wf -o yaml ${WF_NAME} > /tmp/${WF_NAME}.yaml
   ```

   * This requires appropriate K8s RBAC permissions
   * You'll need to be added to the Google group **ci-team@kubeflow.org**

     * Create a PR adding yourself to [ci-team](https://github.com/kubeflow/internal-acls/blob/master/ci-team.members.txt)

1. Search the YAML spec for the pod information for the failed step

   ```
   kubeflow-presubmit-kfctl-1810-70210d5-3900-218a-2243590372:
   boundaryID: kubeflow-presubmit-kfctl-1810-70210d5-3900-218a
   displayName: kfctl-apply-gcp
   finishedAt: 2018-10-17T05:07:58Z
   id: kubeflow-presubmit-kfctl-1810-70210d5-3900-218a-2243590372
   message: failed with exit code 1
   name: kubeflow-presubmit-kfctl-1810-70210d5-3900-218a.kfctl-apply-gcp
   phase: Failed
   startedAt: 2018-10-17T05:04:20Z
   templateName: kfctl-apply-gcp
   type: Pod
   ```

   * You can use displayName to match the text shown in the UI
   * **id** will be the name of the pod.

1. Follow the [instructions](https://github.com/kubeflow/testing#stackdriver-logs) to 
   get the stackdriver logs for the pod.

### Debugging Failed Deployments

If an E2E test fails because a pod doesn't start (e.g JupyterHub) we can debug this by looking at the events associated with the pod.
If you have access to the pod you can do `kubectl describe pods`.

Events are also persisted to StackDriver and can be fetched with a query like the following.

```
resource.labels.cluster_name="kubeflow-testing"
logName="projects/kubeflow-ci/logs/events" 
jsonPayload.involvedObject.namespace = "kubeflow-presubmit-tf-serving-image-299-439a983-360-fa0d"
```

  * Change the namespace to be the actual namespace used for the test

## Testing Changes to the ProwJobs

Changes to our ProwJob configs in [config.yaml](https://github.com/kubernetes/test-infra/blob/master/prow/config.yaml)
should be relatively infrequent since most of the code invoked
as part of our tests lives in the repository.

However, in the event we need to make changes here are some instructions
for testing them.

Follow Prow's
[getting started guide](https://github.com/kubernetes/test-infra/blob/master/prow/getting_started.md)
to create your own prow cluster.

  * **Note** The only part you really need is the ProwJob CRD and controller.

Checkout [kubernetes/test-infra](https://github.com/kubernetes/test-infra).

```
git clone https://github.com/kubernetes/test-infra git_k8s-test-infra
```

Build the mkpj binary

```
bazel build build prow/cmd/mkpj
```

Generate the ProwJob Config

```
./bazel-bin/prow/cmd/mkpj/mkpj --job=$JOB_NAME --config-path=$CONFIG_PATH
```
  * This binary will prompt for needed information like the sha #
  * The output will be a ProwJob spec which can be instantiated using
       kubectl

Create the ProwJob

```
kubectl create -f ${PROW_JOB_YAML_FILE}
```

  * To rerun the job bump metadata.name and status.startTime

To monitor the job open Prow's UI by navigating to the external IP
associated with the ingress for your Prow cluster or using
kubectl proxy.

## Cleaning up leaked resources

Test failures sometimes leave resources (GCP deployments, VMs, GKE clusters) still running. 
The following scripts can be used to garbage collect leaked resources.

```
py/testing/kubeflow/testing/cleanup_ci.py --delete_script=${DELETE_SCRIPT}
```

  * **DELETE_SCRIPT** should be the path to a copy of [delete_deployment.sh](https://github.com/kubeflow/kubeflow/blob/master/scripts/gke/delete_deployment.sh)

There's a second script [cleanup_kubeflow_ci](https://github.com/kubeflow/kubeflow/blob/master/scripts/cleanup_kubeflow_ci.sh)
in the kubeflow repository to cleanup resources left by ingresses.

## Integration with K8s Prow Infrastructure.

We rely on K8s instance of Prow to actually run our jobs.

Here's [a dashboard](https://k8s-testgrid.appspot.com/sig-big-data) with
the results.

Our jobs should be added to
[K8s config](https://github.com/kubernetes/test-infra/blob/master/prow/config.yaml)

## Setting up Kubeflow Test Infrastructure

Our tests require:
  * a K8s cluster
  * Argo installed on the cluster
  * A shared NFS filesystem

Our prow jobs execute Argo worflows in project/clusters owned by Kubeflow. We don't use the shared Kubernetes test clusters for this.
  * This gives us more control of the resources we want to use e.g. GPUs

This section provides the instructions for setting this up.

Create a GKE cluster

```
PROJECT=kubeflow-ci
ZONE=us-east1-d
CLUSTER=kubeflow-testing
NAMESPACE=kubeflow-test-infra

gcloud --project=${PROJECT} container clusters create \
	--zone=${ZONE} \
	--machine-type=n1-standard-8 \
	${CLUSTER}
```

### Create a static ip for the Argo UI

```
gcloud compute --project=${PROJECT} addresses create argo-ui --global
```

### Enable GCP APIs

```
gcloud services --project=${PROJECT} enable cloudbuild.googleapis.com
gcloud services --project=${PROJECT} enable containerregistry.googleapis.com
gcloud services --project=${PROJECT} enable container.googleapis.com
```
### Create a GCP service account

* The tests need a GCP service account to upload data to GCS for Gubernator

```
SERVICE_ACCOUNT=kubeflow-testing
gcloud iam service-accounts --project=${PROJECT} create ${SERVICE_ACCOUNT} --display-name "Kubeflow testing account"
gcloud projects add-iam-policy-binding ${PROJECT} \
    	--member serviceAccount:${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com --role roles/container.admin \
      --role=roles/viewer \
      --role=roles/cloudbuild.builds.editor \
      --role=roles/logging.viewer \
      --role=roles/storage.admin \
      --role=roles/compute.instanceAdmin.v1
```
  * Our tests create K8s resources (e.g. namespaces) which is why we grant it developer permissions.
  * Project Viewer (because GCB requires this with gcloud)
  * Kubernetes Engine Admin (some tests create GKE clusters)
  * Logs viewer (for GCB)
  * Compute Instance Admin to create VMs for minikube
  * Storage Admin (For GCR)


```
GCE_DEFAULT=${PROJECT_NUMBER}-compute@developer.gserviceaccount.com
FULL_SERVICE=${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com
gcloud --project=${PROJECT} iam service-accounts add-iam-policy-binding \
   ${GCE_DEFAULT} --member="serviceAccount:${FULL_SERVICE}" \
   --role=roles/iam.serviceAccountUser
```
  * Service Account User of the Compute Engine Default Service account (to avoid this [error](https://stackoverflow.com/questions/40367866/gcloud-the-user-does-not-have-access-to-service-account-default))


Create a secret key containing a GCP private key for the service account

```
KEY_FILE=<path to key>
SECRET_NAME=gcp-credentials
gcloud iam service-accounts keys create ${KEY_FILE} \
    	--iam-account ${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com
kubectl create secret generic ${SECRET_NAME} \
    --namespace=${NAMESPACE} --from-file=key.json=${KEY_FILE}
```

Make the service account a cluster admin

```
kubectl create clusterrolebinding  ${SERVICE_ACCOUNT}-admin --clusterrole=cluster-admin  \
		--user=${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com
```
* The service account is used to deploye Kubeflow which entails creating various roles; so it needs sufficient RBAC permission to do so.

Add a clusterrolebinding that uses the numeric id of the service account as a work around for
[ksonnet/ksonnet#396](https://github.com/ksonnet/ksonnet/issues/396)


```
NUMERIC_ID=`gcloud --project=kubeflow-ci iam service-accounts describe ${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com --format="value(oauth2ClientId)"`
kubectl create clusterrolebinding  ${SERVICE_ACCOUNT}-numeric-id-admin --clusterrole=cluster-admin  \
    --user=${NUMERIC_ID}
```

### Create a GitHub Token

You need to use a GitHub token with ksonnet otherwise the test quickly runs into GitHub API limits.

TODO(jlewi): We should create a GitHub bot account to use with our tests and then create API tokens for that bot.

You can use the GitHub API to create a token

   * The token doesn't need any scopes because its only accessing public data and is needed only for API metering.

To create the secret run

```
kubectl create secret generic github-token --namespace=${NAMESPACE} --from-literal=github_token=${GITHUB_TOKEN}
```

### Deploy NFS

We use GCP Cloud FileStore to create an NFS filesystem.

There is a deployment manager config in the directory test-infra/gcp_configs

### Create K8s Resources for Testing

The ksonnet app `test-infra` contains ksonnet configs to deploy the test infrastructure.

First, install the kubeflow package

```
ks pkg install kubeflow/core
```

Then change the server ip in `test-infra/environments/prow/spec.json` to
point to your cluster.

You can deploy argo as follows (you don't need to use argo's CLI)

Set up the environment

```
NFS_SERVER=<Internal GCE IP address of the NFS Server>
ks env add ${ENV}
ks param set --env=${ENV} argo namespace ${NAMESPACE}
ks param set --env=${ENV} debug-worker namespace ${NAMESPACE}
ks param set --env=${ENV} nfs-external namespace ${NAMESPACE}
ks param set --env=${ENV} nfs-external nfsServer ${NFS_SERVER}
```

In the testing environment (but not release) we also expose the UI

```
ks param set --env=${ENV} argo exposeUi true
```

```
ks apply ${ENV} -c argo
```

Create the PVs corresponding to external NFS

```
ks apply ${ENV} -c nfs-external
```

#### Troubleshooting

User or service account deploying the test infrastructure needs sufficient permissions to create the roles that are created as part deploying the test infrastructure. So you may need to run the following command before using ksonnet to deploy the test infrastructure.

```
kubectl create clusterrolebinding default-admin --clusterrole=cluster-admin --user=user@gmail.com
```

## Setting up Kubeflow Release Clusters For Testing

We maintain a pool of Kubeflow clusters corresponding to different releases of Kubeflow.
These can be used for

* Running continuous integration of our examples against a particular release
* Manual testing of features in each release

The configs for each deployment are stored in the [test-infra](https://github.com/kubeflow/testing/tree/master/test-infra) directory

The deployments should be named using one of the following patterns

  * `kf-vX.Y-n??` - For clusters corresponding to a particular release
  * `kf-vmaster-n??` - For clusters corresponding to master

This naming scheme is chosen to allow us to cycle through a fixed set of names e.g.

  ```
  kf-v0.4-n00
  ...
  kf-v0.4-n04
  ```
The reason we want to cycle through names is because the endpoint name for the deployment needs to be manually set in the OAuth
credential used for IAP. By cycling through a fixed set of names we can automate redeployment without having to manually
configure the OAuth credential.


1. Get kfctl for the desired release
1. Run the following command

   ```
   python -m kubeflow.testing.create_kf_instance --base_name=<kf-vX.Y|kf-vmaster>
   ```
1. Create a PR with the resulting config.  

## Setting up a Kubeflow Repository to Use Prow <a id="prow-setup"></a>


1. Define ProwJobs see [pull/4951](https://github.com/kubernetes/test-infra/pull/4951)

    * Add prow jobs to [prow/config.yaml](https://github.com/kubernetes/test-infra/pull/4951/files#diff-406185368ba7839d1459d3d51424f104)
    * Add trigger plugin to [prow/plugins.yaml](https://github.com/kubernetes/test-infra/pull/4951/files#diff-ae83e55ccb05896d5229df577d34255d)
    * Add test dashboards to [testgrid/config.yaml](https://github.com/kubernetes/test-infra/pull/4951/files#diff-49f154cd90facc43fda49a99885e6d17)
    * Modify testgrid/cmd/configurator/config_test.go
       to allow presubmits for the new repo.
1. Add the `ci-bots` team to the repository with write access
    * Write access will allow bots in the team to update status
1. Follow [instructions](https://github.com/kubernetes/test-infra/tree/master/gubernator#adding-a-repository-to-the-pr-dashboard) for adding a repository to the PR
   dashboard.
1. Add an `OWNERS` to your Kubeflow repository.  The `OWNERS` file, like [this one](https://github.com/kubeflow/kubeflow/blob/master/OWNERS), will specify who can review and approve on this repo.


Webhooks for prow should already be configured according to these [instructions](https://github.com/kubernetes/test-infra/blob/master/prow/getting_started.md#add-the-webhook-to-github) for the org so you shouldn't
need to set hooks per repository.
    * Use https://prow.k8s.io/hook as the target
    * Get HMAC token from k8s test team

## Writing An Argo Workflow For An E2E Test

This section provides guidelines for writing Argo workflows to use as E2E tests

This guide is complementary to the [E2E testing guide for TFJob operator](https://github.com/kubeflow/tf-operator/blob/master/e2e_testing.md)
which describes how to author tests to performed as individual steps in the workflow.

Some examples to look at

  * [gis.jsonnet](https://github.com/kubeflow/examples/blob/master/test/workflows/components/gis.jsonnet) in kubeflow/examples


### Adding an E2E test to a repository

Follow these steps to add a new test to a repository.

1. Create a ksonnet App in that repository and define an Argo workflow if one doesn't already exist
   * We use ksonnet apps defined in each repository to define the Argo workflows corresponding to E2E tests
   * If a ksonnet app already exists you can just define a new component in that app

     1. Create a .jsonnet file (e.g by copying an existing .jsonnet file)

        * Change the import for the params to use the newly defined component

        * See [gis.jsonnet in kubeflow/examples#449](https://github.com/kubeflow/examples/blob/d99abc23d10851fe8f3a19732ab5078f5edc0397/test/workflows/components/gis.jsonnet)

     1. Update the `params.libsonnet` to add a stanza to define params for the new component

       * See [params.jsonnet in kubeflow/examples#449](https://github.com/kubeflow/examples/blob/d99abc23d10851fe8f3a19732ab5078f5edc0397/test/workflows/components/params.libsonnet)

   * You can look at `prow_config.yaml` (see below) to see which ksonnet apps are already defined in a repository.

1. Modify the `prow_config.yaml` at the root of the repo to trigger your new test.

   * If `prow_config.yaml` doesn't exist (e.g. the repository is new) copy one from an existing repository ([example](https://github.com/kubeflow/kubeflow/blob/master/prow_config.yaml)).
     
   * `prow_config.yaml` contains an array of workflows where each workflow defines an E2E test to run; example

       ```
       workflows:
        - app_dir: kubeflow/testing/workflows
          component: workflows
          name: unittests
          job_types:
            - presubmit
          include_dirs:
            - foo/*
            - bar/*
              params:
          params:
            platform: gke
            gkeApiVersion: v1beta1
       ```

       * **app_dir**: Is the path to the ksonnet directory within the repository. This should be of the form `${GITHUB_ORG}/${GITHUB_REPO_NAME}/${PATH_WITHIN_REPO_TO_KS_APP}`
       * **component**: This is the name of the ksonnet component to use for the Argo workflow
       * **name**: This is the base name to use for the submitted Argo workflow.         

         * The test infrastructure appends a suffix of 22 characters (see [here](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/run_e2e_workflow.py#L196))
         
         * The result is passed to your ksonnet component via the name parameter

         * Your ksonnet component should truncate the name if necessary to satisfy
           K8s naming constraints.

           * e.g. Argo workflow names should be less than 63 characters because
             they are used as pod labels

       * **job_types**: This is an array specifying for which types of [prow jobs](https://github.com/kubernetes/test-infra/blob/master/prow/jobs.md)
          this workflow should be triggered on.

          * Currently allowed values are **presubmit**, **postsubmit**, and **periodic**.

      * **include_dirs**: If specified, the pre and postsubmit jobs will only trigger this test if the PR changed at least one file matching at least one
         of the listed directories.

         * Python's [fnmatch function](https://docs.python.org/2/library/fnmatch.html) is used to compare the listed patterns against the full path
           of modified files (see [here](https://github.com/kubeflow/testing/blob/46c5d0daa6d161e52f61b8fcaa448870945bea6d/py/kubeflow/testing/run_e2e_workflow.py#L181))

         * This functionality should be used to ensure that expensive tests are only run when test impacting changes are made; particularly if its an expensive or flaky presubmit

         * periodic runs ignore **include_dirs**; a periodic run will trigger all
           workflows that include job_type **periodic**

      * A given ksonnet component can have multiple workflow entries to allow different
        triggering conditions on pre/postsubmit

        * For example, on presubmit we might run a test on a single platform (GKE) but on
          postsubmit that same test might run on GKE and minikube
        * this can be accomplished with different entries pointing at the same ksonnet
          component but with different `job_types` and `params`.

     * **params**: A dictionary of parameters to set on the ksonnet component e.g. by running `ks param set ${COMPONENT} ${PARAM_NAME} ${PARAM_VALUE}`


### Prow Variables

* For each test run PROW defines several variables that pass useful information to your job.

* The list of variables is defined [in the prow docs](https://github.com/kubernetes/test-infra/blob/master/prow/jobs.md#job-environment-variables).

* These variables are often used to assign unique names to each test run to ensure isolation (e.g. by appending the BUILD_NUMBER)

* The prow variables are passed via ksonnet parameter `prow_env` to your workflows

  * You can copy the macros defined in [util.libsonnet](https://github.com/kubeflow/examples/blob/70a22d6d7bbb8bf126cc581d89d6cf40937e07f5/test/workflows/components/util.libsonnet#L30)
    to parse the ksonnet parameter into a jsonnet map that can be used in your workflow.

  * **Important** Always define defaults for the prow variables in the dict e.g. like

    ```
    local prowDict = {
      BUILD_ID: "notset",
      BUILD_NUMBER: "notset",
      REPO_OWNER: "notset",
      REPO_NAME: "notset",
      JOB_NAME: "notset",
      JOB_TYPE: "notset",
      PULL_NUMBER: "notset",  
     } + util.listOfDictToMap(prowEnv);
    ```

    * This prevents jsonnet from failing in a hard to debug way in the event that you try to access a key which is not in the map.

### Argo Spec

* Guard against long names by truncating the name and using the BUILD_ID to ensure the
  name remains unique e.g

  ```
  local name = std.substr(params.name, 0, std.min(58, std.lenght(params.name))) + "-" + prowDict["BUILD_ID"];            
  ```

  * Argo workflow names need to be less than 63 characters because they are used as pod 
    labels

  * BUILD_ID are unique for each run per repo; we suggest reserving 5 characters for
    the BUILD_ID.

* Argo workflows should have standard labels corresponding to prow variables; for example

  ```
  labels: prowDict + {    
    workflow_template: "code_search",    
  },
  ```

  * This makes it easy to query for Argo workflows based on prow job info.
  * In addition the convention is to use the following labels

    * **workflow_template**: The name of the ksonnet component from which the workflow is created.

* The templates for the individual steps in the argo workflow should also have standard labels

  ```
  labels: prowDict + {
    step_name: stepName,
    workflow_template: "code_search",
    workflow: workflowName,
  },
  ```

  * **step_name**: Name of the step (e.g. what shows up in the Argo graph)
  * **workflow_template**: The name of the ksonnet component from which the workflow is created.
  * **workflow**: The name of the Argo workflow that owns this pod.


* Following the above conventions make it very easy to get logs for specific steps

  ```
  kubectl logs -l step_name=checkout,REPO_OWNER=kubeflow,REPO_NAME=examples,BUILD_ID=0104-064201 -c main

  ```

### Creating K8s resources in tests.

Tests often need a K8s/Kubeflow deployment on which to create resources and run various tests.

Depending on the change being tested

  * The test might need exclusive access to a Kubeflow/Kubernetes cluster

    * e.g. Testing a change to a custom resource usually requires exclusive access to a K8s cluster 
      because only one CRD and controller can be installed per cluster. So trying to test two different
      changes to an operator (e.g. tf-operator) on the same cluster is not good.

  * The test might need a Kubeflow/K8s deployment but doesn't need exclusive access

    * e.g. When running tests for Kubeflow examples we can isolate each test using namespaces or
      other mechanisms.

* If the test needs exclusive access to the Kubernetes cluster then there should be a step in the workflow 
  that creates a KubeConfig file to talk to the cluster.

  * e.g. E2E tests for most operators should probably spin up a new Kubeflow cluster

* If the test just needs a known version of Kubeflow (e.g. master or v0.4) then it should use
  one of the test clusters in project kubeflow-ci for this

  * The infrasture to support this is not fully implemented see [kubeflow/testing#95](https://github.com/kubeflow/testing/issues/95)
    and [kubeflow/testing#273](https://github.com/kubeflow/testing/issues/273)


To connect to the cluster:
  * The Argo workflow should have a step that configures the `KUBE_CONFIG` file to talk to the cluster

    * e.g. by running `gcloud container clusters get-credentials`

  * The Kubeconfig file should be stored in the NFS test directory so it can be used in subsequent steps
  * Set the environment variable `KUBE_CONFIG` on your steps to use the KubeConfig file

### NFS Directory

An NFS volume is used to create a shared filesystem between steps in the workflow.

* Your Argo workflows should use a PVC claim to mount the NFS filesystem into each step

  * The current PVC name is `nfs-external`
  * This should be a parameter to allow different PVC names in different environments.

* Use the following directory structure 

  ```
  ${MOUNT_POINT}/${WORKFLOW_NAME}
                                 /src
                                     /${REPO_ORG}/${REPO_NAME}
                                 /outputs
                                 /outputs/artifacts
  ```

  * **MOUNT_PATH**: Location inside the pod where the NFS volume is mounted
  * **WORKFLOW_NAME**: The name of the Argo workflow
    * Each Argo workflow job has a unique name (enforced by APIServer)
    * So using WORKFLOW_NAME as root for all results associated with a particular job ensures there
      are no conflicts
  * **/src**: Any repositories that are checked out should be checked out here
     * Each repo should be checked out to the sub-directory **${REPO_ORG}/${REPO_NAME}**
  * **/outputs**: Any files that should be sync'd to GCS for Gubernator should be written here

### Step Image

* The Docker image used by the Argo steps should be a ksonnet parameter `stepImage`
* The Docker image should use an immutable image tag e.g `gcr.io/kubeflow-ci/test-worker:v20181017-bfeaaf5-dirty-4adcd0`

  * This ensures tests don't break if someone pushes a new test image

* The ksonnet parameter `stepImage` should be set in the `prow_config.yaml` file defining the E2E tests

  * This makes it easy to update all the workflows to use some new image.

* A common runtime is defined [here](https://github.com/kubeflow/testing/tree/master/images) and published to 
  [gcr.io/kubeflow-ci/test-worker](https://gcr.io/kubeflow-ci/test-worker)


### Checking out code

* The first step in the Argo workflow should checkout out the source repos to the NFS directory
* Use [checkout.sh](https://github.com/kubeflow/testing/blob/master/images/checkout.sh) to checkout the repos  
* checkout.sh environment variable `EXTRA_REPOS` allows checking out additional repositories in addition
  to the repository that triggered the pre/post submit test

  * This allows your test to use source code located in a different repository
  * You can specify whether to checkout the repository at HEAD or pin to a specific commit

* Most E2E tests will want to checkout kubeflow/testing in order to use various test utilities


### Building Docker Images

There are lots of different ways to build Docker images (e.g. GCB, Docker in Docker). Current recommendation
is

* Define a Makefile to provide a convenient way to invoke Docker builds
* Using Google Container Builder (GCB) to run builds in Kubeflow's CI system generally works better
  than alternatives (e.g. Docker in Docker, Kaniko)

  * Your Makefile can have alternative rules to support building locally via Docker for developers

* Use jsonnet if needed to define GCB workflows

  * Example [jsonnet file](https://github.com/kubeflow/examples/blob/master/code_search/docker/t2t/build.jsonnet)
    and associated [Makefile](https://github.com/kubeflow/examples/blob/master/code_search/Makefile)

* Makefile should expose variables for the following

  * Registry where image is pushed
  * TAG used for the images

* Argo workflow should define the image paths and tag so that subsequent steps can use the newly built images
