<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Working with GCP test infrastructure](#working-with-gcp-test-infrastructure)
- [Logs](#logs)
  - [Prow](#prow)
  - [Argo UI](#argo-ui)
  - [Stackdriver logs](#stackdriver-logs)
- [Debugging Failed Tests](#debugging-failed-tests)
  - [Logs and Cluster Access for Kubeflow CI](#logs-and-cluster-access-for-kubeflow-ci)
    - [Access Control](#access-control)
  - [No results show up in Spyglass](#no-results-show-up-in-spyglass)
  - [No Logs in Argo UI For Step or Pod Id missing in Argo Logs](#no-logs-in-argo-ui-for-step-or-pod-id-missing-in-argo-logs)
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
  - [Creating secret for deployapp test](#creating-secret-for-deployapp-test)
  - [Troubleshooting](#troubleshooting)
- [Setting up Kubeflow Release Clusters For Testing](#setting-up-kubeflow-release-clusters-for-testing)
- [Setting up a Kubeflow Repository to Use Prow <a id="prow-setup"></a>](#setting-up-a-kubeflow-repository-to-use-prow-a-idprow-setupa)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Working with GCP test infrastructure

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

The logs from each step are copied to GCS and made available through spyglass. The K8s-ci robot should post
a link to the spyglass UI in the PR. You can also find them as follows

1. Open up the prow jobs dashboard e.g. [for kubeflow/kubeflow](https://prow.k8s.io/?repo=kubeflow%2Fkubeflow)
1. Find your job
1. Click on the link under job; this goes to the Gubernator dashboard
1. Click on artifacts
1. Navigate to artifacts/logs

If these logs aren't available it could indicate a problem running the step that uploads the artifacts to GCS for spyglass. In this
case you can use one of the alternative methods listed below.

### Argo UI

The argo UI is publicly accessible at http://testing-argo.kubeflow.org/timeline.

1. Find and click on the workflow corresponding to your pre/post/periodic job
1. Select the workflow tab
1. From here you can select a specific step and then see the logs for that step

### Stackdriver logs

Since we run our E2E tests on GKE, all logs are persisted in [Stackdriver logging](https://pantheon.corp.google.com/logs/viewer?project=kubeflow-ci&organizationId=714441643818&minLogLevel=0&expandAll=false&timestamp=2019-02-12T13:52:11.264000000Z&customFacets=&limitCustomFacetWidth=true&dateRangeStart=2019-02-12T12:52:20.819Z&dateRangeEnd=2019-02-12T13:52:20.819Z&interval=PT1H&resource=k8s_container%2Fcluster_name%2Fkf-v0-4-n00%2Fnamespace_name%2Fkubeflow%2Fcontainer_name%2Ftensorflow&advancedFilter=resource.type%3D"k8s_container"%0Aresource.labels.cluster_name%3D"kubeflow-testing").

Viewer access to Stackdriver logs is available by joining one of the following groups

  * ci-viewer@kubeflow.org
  * ci-team@kubeflow.org


We use the new stackdriver Kubernetes logging which means we use the [k8s_pod](https://cloud.google.com/monitoring/api/resources#tag_k8s_pod)
 and [k8s_container](https://cloud.google.com/monitoring/api/resources#tag_k8s_container) resource types.


Below are some relevant filters:

Get container logs for a specific pod

```
resource.type="k8s_container"
resource.labels.cluster_name="kubeflow-testing"
resource.labels.pod_name="${POD_NAME}"
```

Get logs using pod label

```
resource.type="k8s_container"
resource.labels.cluster_name="kubeflow-testing"
metadata.userLabels.${LABEL_KEY}="${LABEL_VALUE}"
```

Get events for a pod

```
resource.type="k8s_pod"
resource.labels.cluster_name="${CLUSTER}"
resource.labels.pod_name="${POD_NAME}"
```

The [Kubeflow docs](https://www.kubeflow.org/docs/other-guides/monitoring/#stackdriver-kubernetes) have some useful
gcloud one liners for fetching logs.

## Debugging Failed Tests

### Logs and Cluster Access for Kubeflow CI

Our tests are split across three projects

* **k8s-prow-builds**

  * This is owned by the prow team
  * This is where the prow jobs are defined
   
* **kubeflow-ci**

  * This is where the prow jobs run in the `test-pods` namespace
  * This is where the Argo E2E workflows kicked off by the prow jobs run
  * This is where other Kubeflow test infra (e.g. various cron jobs run)

* **kubeflow-ci-deployment**

   * This is the project where E2E tests actually create Kubeflow clusters


#### Access Control 

We currently have the following levels of access

* **ci-viewer-only**

  * This is controlled by the group [ci-viewer](https://github.com/kubeflow/internal-acls/blob/master/ci-viewer.members.txt)

  * This group basically grants viewer only access to projects **kubeflow-ci** and **kubeflow-ci-deployment**
  * This provides access to stackdriver for both projects

  * Folks making regular and continual contributions to Kubeflow and in need of access to debug
    tests can generally have access

* **ci-edit/admin** 

  * This is controlled by the group [ci-team](https://github.com/kubeflow/internal-acls/blob/master/ci-team.members.txt)

  * This group grants permissions necessary to administer the infrastructure running in **kubeflow-ci** and **kubeflow-ci-deployment**

  * Access to this group is highly restricted since this is critical infrastructure for the project

  * Following standard operating procedures we want to limit the number of folks with direct access to infrastructure

    * Rather than granting more people access we want to develop scalable practices that eliminate the need for
      granting large numbers of people access (e.g. developing git ops processes)

 * **example-maintainers**

   * This is controlled by the group [example-maintainers](https://github.com/kubeflow/internal-acls/blob/master/example-maintainers.members.txt)

   * This group provides more direct access to the Kubeflow clusters running **kubeflow-ci-deployment**

   * This group is intended for the folks actively developing and maintaining tests for Kubeflow examples

   * Continuous testing for kubeflow examples should run against regularly updated, auto-deployed clusters in project **kubeflow-ci-deployment**

     * Example maintainers are granted elevated access to these clusters in order to facilitate development of these tests

### No results show up in Spyglass

If no results show up in Spyglass this means the prow job didn't get far enough to upload any results/logs to GCS.

To debug this you need the pod logs. You can access the pod logs via the build log link for your job in the [prow jobs UI](https://prow.k8s.io/)

  * Pod logs are ephemeral so you need to check shortly after your job runs.

The pod logs are available in StackDriver but only the Google Kubeflow Team has access
  * Prow controllers run on a cluster (`k8s-prow/prow`) owned by the K8s team
  * Prow jobs (i.e. pods) run on a build cluster (`kubeflow-ci/kubeflow-testing`) owned by the Kubeflow team
  * This policy for controller logs is owned by K8s, while the policy for job logs is governed by Kubeflow

To access the stackdriver logs 
  
  * Open stackdriver for project [kubeflow-ci](https://console.cloud.google.com/logs/viewer?organizationId=433637338589&project=kubeflow-ci&minLogLevel=0&expandAll=false&customFacets=&limitCustomFacetWidth=true&interval=P7D&resource=k8s_container%2Fcluster_name%2Fkubeflow-testing%2Fnamespace_name%2Ftest-pods&advancedFilter=resource.type%3D%22k8s_container%22%0Aresource.labels.cluster_name%3D%22kubeflow-testing%22%0Aresource.labels.namespace_name%3D%22test-pods%22%0Aresource.labels.pod_name%3D%22bc2f6d5d-7035-11ea-bd6a-f29ce8b0e481%22%0A)
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

### No Logs in Argo UI For Step or Pod Id missing in Argo Logs

The Argo UI will surface logs for the pod but only if the pod hasn't been deleted yet by Kubernetes.

Using stackdriver to fetch pod logs is more reliable/durable but requires viewer permissions for Kubeflow's ci's infrastructure.

An Argo workflow fails and you click on the failed step in the Argo UI to get the logs
and you see the error

```bash
failed to get container status {"docker" "b84b751b0102b5658080a520c9a5c2655855960c4695cf557c0c1e45999f7429"}: 
rpc error: code = Unknown desc = Error: No such container: b84b751b0102b5658080a520c9a5c2655855960c4695cf557c0c1e45999f7429
```

This error is a red herring; it means the pod is probably gone so Argo couldn't get the logs.

The logs should be in StackDriver but to get them we need to identify the pod.

1. Get the workflow spec:

   - Get the workflow YAML using kubectl

     ```bash
     kubectl get wf -o yaml ${WF_NAME} > /tmp/${WF_NAME}.yaml
     ```

     - This requires appropriate K8s RBAC permissions
     - You'll need to be added to the Google group **ci-team@kubeflow.org**
     - Create a PR adding yourself to [ci-team](https://github.com/kubeflow/internal-acls/blob/master/ci-team.members.txt)
     - Add credentials to your $HOME/.kube/config: `gcloud --project kubeflow-ci container clusters get-credentials kubeflow-testing --zone us-east1-d`

   - Get the workflow YAML from Prow artifacts
     - Find your Prow job from <https://prow.k8s.io/?repo=kubeflow%2Ftesting>.
     - Find the artifacts from the Spyglass link of the Prow job, e.g. <https://prow.k8s.io/view/gcs/kubernetes-jenkins/pr-logs/pull/kubeflow_testing/360/kubeflow-testing-presubmit/1120174107468500992/>.
     - Download `${WF_NAME}.yaml` from the GCS artifacts page.

2. Search the YAML spec for the pod information for the failed step

   - We need to find information that can be used to fetch logs for the pod from stackdriver

     1. Using Pod labels

        - In the workflow spec look at the step metadata to see if it contains labels

          ```yaml
          metadata:
            labels:
              BUILD_ID: "1405"
              BUILD_NUMBER: "1405"
              JOB_NAME: kubeflow-examples-presubmit
              JOB_TYPE: presubmit
              PULL_BASE_SHA: 8a26b23e3d35d5993d93e8b9ecae52371598d1cc
              PULL_NUMBER: "522"
              PULL_PULL_SHA: 9aecf80f1c41059cd8ff13d1ca8b9e821dc462bf
              REPO_NAME: examples
              REPO_OWNER: kubeflow
              step_name: tfjob-test
              workflow: kubeflow-examples-presubmit-gis-522-9aecf80-1405-9055
              workflow_template: gis
          ```

        - Follow the [stackdriver instructions](https://github.com/kubeflow/testing#stackdriver-logs) to query for the logs
          - Use labels `BUILD_ID` and `step_name` to identify the pod

     2. If no labels are specified for the step you can use displayName to match the text in the UI to 
         step status

         ```yaml
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

         - **id** will be the name of the pod.

         - Follow the [instructions](https://github.com/kubeflow/testing#stackdriver-logs) to get the stackdriver logs for the pod or use the following gcloud command

           ```bash
             gcloud --project=kubeflow-ci logging read --format="table(timestamp, resource.labels.container_name, textPayload)" \
             --freshness=24h \
             --order asc  \
             "resource.type=\"k8s_container\" resource.labels.pod_name=\"${POD}\"  "
           ```

### Debugging Failed Deployments

If an E2E test fails because one of the Kubeflow applications (e.g. the Jupyter web app)
isn't reported as deploying successfully we can follow these instructions to debug it.

To debug it we want to look at the K8s events indicating why the K8s deployment failed.
In most cases the cluster will already be torn down so we need to look at the
kubernetes events associated with that deployment.


1. Get the cluster used for Kubeflow

   1. In prow look at artifacts and find the YAML spec for the Argo workflow that
      ran your e2e test

   1. Identify the step that deployed Kubeflow

   1. Open up [stack driver logging](https://console.cloud.google.com/logs/viewer?project=kubeflow-ci-deployment&_ga=2.20425662.-720060064.1532059791&_gac=1.95560430.1553366450.CjwKCAjwstfkBRBoEiwADTmnEHB4EsCQkymxInUJfA875uharmvOzl6RadXtmxRqVYzya7mIGRmEERoC5-kQAvD_BwE&minLogLevel=0&expandAll=false&timestamp=2019-04-29T15:58:54.719000000Z&customFacets=&limitCustomFacetWidth=true&dateRangeStart=2019-04-22T16:33:20.360Z&dateRangeEnd=2019-04-29T16:33:20.360Z&interval=P7D&resource=k8s_container%2Fcluster_name%2Fkf-v0-4-n00%2Fnamespace_name%2Fkubeflow%2Fcontainer_name%2Ftensorflow&scrollTimestamp=2019-04-27T01:15:15.949166770Z&advancedFilter=resource.type%3D%22k8s_container%22%0Aresource.labels.pod_name%3D%22kubeflow-presubmit-kfctl-go-iap-3066-6266699-3248-6742-3522306767%22%0Aresource.labels.container_name%3D%22main%22%0Aget-credentials)

   1. Use a filter (advanced) like the following to find the log entry getting the credentials for your deployment

      ```
      resource.type="k8s_container"
      resource.labels.pod_name=`<POD NAME>`
      resource.labels.container_name="main"
      get-credentials
      ```

   1. The log output should look like the following

      ```
      get-credentials kfctl-6742 --zone=us-east1-d --project=kubeflow-ci-deployment 
      ```

       * The argument `kfctl-6742` is the name of the cluster

1. You can use the script `py/kubeflow/testing/troubleshoot_deployment.py` to fetch logs alternatively you 
   can follow the steps below to filter the logs in the stackdriver UI

1. Use a filter like the [following](https://console.cloud.google.com/logs/viewer?project=kubeflow-ci-deployment&organizationId=714441643818&minLogLevel=0&expandAll=false&customFacets&limitCustomFacetWidth=true&interval=NO_LIMIT&resource=gce_instance_group%2Finstance_group_id%2F1008177806084829541%2Finstance_group_name%2Fk8s-ig--53fc5e0363ccb918&advancedFilter=resource.labels.cluster_name%3D%22kfctl-6742%22%0AlogName%3D%22projects%2Fkubeflow-ci-deployment%2Flogs%2Fevents%22%20%0AjsonPayload.involvedObject.name%3D%22jupyter-web-app%22&scrollTimestamp=2019-04-27T01%3A23%3A48.000000000Z) to get the events associated with the deployment or statefulset

   ```
    resource.labels.cluster_name="kfctl-6742"
    logName="projects/kubeflow-ci-deployment/logs/events" 
    jsonPayload.involvedObject.name="jupyter-web-app"
   ```      

   * Change the name of the involvedObject and cluster name to match your deployment.

   * If a pod was created the name of the pod should be present e.g.

     ```
     Scaled up replica set jupyter-web-app-5fcddbf75c to 1"
     ```

   * You can continue to look at event logs for the replica set to eventually get to the name of a pod and potentially
     the pod.

## Testing Changes to the ProwJobs

Changes to our ProwJob configs in [config.yaml](https://github.com/kubernetes/test-infra/blob/master/config/prow/config.yaml)
should be relatively infrequent since most of the code invoked
as part of our tests lives in the repository.

However, in the event we need to make changes here are some instructions
for testing them.

Follow Prow's
[getting started guide](https://github.com/kubernetes/test-infra/tree/master/prow#getting-started)
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
The following scripts for example can be used to garbage collect all resources. The
script can GC specific resources with different commands.

```
cd py
python -m kubeflow.testing.cleanup_ci --project kubeflow-ci-deployment all
```

This script is set up as a cronjob by `cd test-infra/cleanup && make hydrate`.

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

### Creating secret for deployapp test

The e2e test that runs click-to-deploy app will test deploying kubeflow to a cluter
under project kubeflow-ci-deployment.
So it needs to know a clientID and secret of that project.
Check out this [page](https://pantheon.corp.google.com/apis/credentials?project=kubeflow-ci-deployment&folder&organizationId=714441643818)
and look for client ID called deployapp-test-client.

```
kubectl create secret generic --namespace=${NAMESPACE} kubeflow-oauth --from-literal=client_id=${CLIENT_ID} --from-literal=client_secret=${CLIENT_SECRET}
```

### Troubleshooting

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

