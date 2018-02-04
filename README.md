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
  
This is a work in progress see [kubeflow/kubeflow#38](https://github.com/kubeflow/kubeflow/issues/38)

  * Prow will be used to trigger E2E tests
  * The E2E test will launch an Argo workflow that describes the tests to run
  * Each step in the Argo workflow will be a binary invoked inside a container
  * The Argo workflow will use an NFS volume to attach a shared POSIX compliant filesystem to each step in the
    workflow.
  * Each step in the pipeline can write outputs and junit.xml files to a test directory in the volume
  * A final step in the Argo pipeline will upload the outputs to GCS so they are available in gubernator

## Anatomy of our Tests

* Our prow jobs are defined in [config.yaml](https://github.com/kubernetes/test-infra/blob/master/prow/config.yaml)
* Each prow job defines a K8s PodSpec indicating a command to run
* Our prow jobs use [run_e2e_workflow.py](https://github.com/py/kubeflow/testing/run_e2e_workflow.py
) to trigger an Airflow pipeline that checks out our code and runs our Tests.
* Our tests are structured as Argo pipelines so that we can easily perform steps in parallel.

## Accessing The Argo UI

The UI is publicly available at http://http://testing-argo.kubeflow.io/

## Working with the test infrastructure

The tests store the results of tests in a shared NFS filesystem. To inspect the results you can mount the NFS volume.

To facilitate that, run a stateful set that mounts the same volumes as our Argo workers. Furthermore, this stateful set
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

If these logs aren't available it could indicate a problem that prevent logs from being uploaded correctly to GCS for gubernator.

### Argo UI

The argo UI is publicly accessible at http://testing-argo.kubeflow.io/timeline.

1. Find and click on the workflow corresponding to your pre/post/periodic job
1. Select the workflow tab
1. From here you can select a specific step and then see the logs for that step

Unfortunately there are some limitations in the Argo UI e.g.
 
  * [argo/issues#710](https://github.com/argoproj/argo/issues/710) exit handlers aren't shown

So if your exit handler fails you may need to look at pod logs or stackdriver logs directly.

### StackDriver logs

Since we run our E2E tests on GKE, all logs are persisted in Stackdriver logging.

Access to Stackdriver logs is restricted. We are working on giving sufficient access to members of the community ([kubeflow/testing#5](https://github.com/kubeflow/testing/issues/5).

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

## Adding an E2E test for a new repository

We use prow to launch Argo workflows. Here are the steps to create a new E2E test for a new repository

1. Create a ksonnet App in that repository and define an Argo workflow
1. Create a prow job for that repository

To generate the PodTemplate spec for the job you can use our sample ksonnet app.

```
RPATH=<Path relative to the root of your github repo to the directory containing the ksonnet app with your Argo workflows for E2E tests.>
APP_DIR=/src/${RPATH}
TEST_SUBDIR=<The relative path in your repo where kubeflow/testing is checked out as a submodule
COMPONENT=<The name of the component in your ksonnet APP for your Argo workflow>
cd sample-app
ks param set prow_env ""
ks param set app_dir ${APP_DIR}
ks param set component ${COMPONENT}
ks param set testing_subdir ${TEST_SUBDIR}
ks show test -c prow_pod
```
 
  * You can use spec.template.spec as the pod spec for the prow job.

To actually test it you can run it

```
BUILD_NUMBER=$(uuidgen); BUILD_NUMBER=${BUILD_NUMBER:0:4}; echo ${BUILD_NUMBER}
ks param set prow_env "JOB_NAME=tf-k8s-presubmit,JOB_TYPE=presubmit,PULL_NUMBER=358,REPO_NAME=k8s,REPO_OWNER=tensorflow,BUILD_NUMBER=$(BUILDNUMBER)"
ks apply test -c prow_pod
```
  * Change the values as needed to point it at the repo you want to use

TODO(jlewi): We should consider just running [plank](https://github.com/kubernetes/test-infra/tree/master/prow/cmd) and then using the tool mkpj to create the prow job to test it.

## Testing Changes to the ProwJobs

Changes to our ProwJob configs in [config.yaml](https://github.com/kubernetes/test-infra/blob/master/prow/config.yaml)
should be relatively infrequent since most of the code invoked
as part of our tests lives in the repository.

However, in the event we need to make changes here are some instructions
for testing them.

Follow Prow's
[getting started guide](https://github.com/kubernetes/test-infra/blob/master/prow/getting_started.md)
to create your own prow cluster.

    * TODO(jlewi): We don't really need the ingress. You can connect
      over kubectl or some other mechanism.

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

## Integration with K8s Prow Infrastructure.

We rely on K8s instance of Prow to actually run our jobs.

Here's [a dashboard](https://k8s-testgrid.appspot.com/sig-big-data) with
the results.

Our jobs should be added to
[K8s config](https://github.com/kubernetes/test-infra/blob/master/prow/config.yaml)

## Setting up the Test Infrastructure

Our tests require a K8s cluster with Argo installed. This section provides the instructions
for setting this.

Create a GKE cluster

```
PROJECT=mlkube-testing
ZONE=us-east1-d
CLUSTER=kubeflow-testing
NAMESPACE=kubeflow-test-infra

gcloud --project=${PROJECT} container clusters create \
	--zone=${ZONE} \
	--machine-type=n1-standard-8 \
	--cluster-version=1.8.4-gke.1 \
	${CLUSTER}
```


### Create a GCP service account

* The tests need a GCP service account to upload data to GCS for Gubernator

```
SERVICE_ACCOUNT=kubeflow-testing
gcloud iam service-accounts --project=mlkube-testing create ${SERVICE_ACCOUNT} --display-name "Kubeflow testing account"
	gcloud projects add-iam-policy-binding ${PROJECT} \
    	--member serviceAccount:${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com --role roles/container.developer
```
* The service account needs to be able to create K8s resources as part of the test.


Create a secret key for the service account

```
gcloud iam service-accounts keys create ~/tmp/key.json \
    	--iam-account ${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com
    kubectl create secret generic kubeflow-testing-credentials \
        --namespace=kubeflow-test-infra --from-file=`echo ~/tmp/key.json`
    rm ~/tmp/key.json
```

Make the service account a cluster admin

```
kubectl create clusterrolebinding  ${SERVICE_ACCOUNT}-admin --clusterrole=cluster-admin  \
		--user=${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com
```
* The service account is used to deploye Kubeflow which entails creating various roles; so it needs sufficient RBAC permission to do so.

The service account also needs the following GCP privileges because various tests use them

  * Project Viewer (because GCB requires this with gcloud)
  * Cloud Container Builder
  * Kubernetes Engine Admin (some tests create GKE clusters)
  * Logs viewer
  * Storage Admin
  * Service Account User of the Compute Engine Default Service account (to avoid this [error](https://stackoverflow.com/questions/40367866/gcloud-the-user-does-not-have-access-to-service-account-default))

### Create a GitHub Token

You need to use a GitHub token with ksonnet otherwise the test quickly runs into GitHub API limits.

TODO(jlewi): We should create a GitHub bot account to use with our tests and then create API tokens for that bot.

You can use the GitHub API to create a token

   * The token doesn't need any scopes because its only accessing public data and is just need for API metering.

To create the secret run

```
kubectl create secret generic github-token --namespace=kubeflow-test-infra --from-literal=github_token=${TOKEN}
```

### Deploy NFS

We use GCP Cloud Launcher to create a single node NFS share; current settings

  * 8 VCPU
  * 1 TB disk

### Create a PD for NFS

**Note** We are in the process of migrating to using an NFS share outside the GKE cluster. Once we move
kubeflow/kubeflow to that we can get rid of this section.

Create a PD to act as the backing storage for the NFS filesystem that will be used to store data from
the test runs.

```
  gcloud --project=${PROJECT} compute disks create  \
  	--zone=${ZONE} kubeflow-testing --description="PD to back NFS storage for kubeflow testing." --size=1TB
```
### Create K8s Resources for Testing

The ksonnet app `test-infra` contains ksonnet configs to deploy the test infrastructure.

First, install the kubeflow package

```
ks pkg install kubeflow/core
```

Then change the server ip in `test-infra/environments/prow/spec.json` to
point to your cluster.

You can deploy argo as follows (you don't need to use argo's CLI)

```
ks apply prow -c argo
```

Create the PVs corresponding to external NFS

```
ks apply prow -c nfs-external
```

Deploy NFS & Jupyter

```
ks apply prow -c nfs-jupyter
```

* This creates the NFS share
* We use JupyterHub as a convenient way to access the NFS share for manual inspection of the file contents.

#### Troubleshooting

User or service account deploying the test infrastructure needs sufficient permissions to create the roles that are created as part deploying the test infrastructure. So you may need to run the following command before using ksonnet to deploy the test infrastructure.

```
kubectl create clusterrolebinding default-admin --clusterrole=cluster-admin --user=user@gmail.com
```

## Setting up K8s Prow Instance For A Kubeflow Repository

Below is some notes on what it took to integrate with K8s Prow instance.

1. Define ProwJobs see [pull/4951](https://github.com/kubernetes/test-infra/pull/4951)

    * Add prow jobs to [prow/config.yaml](https://github.com/kubernetes/test-infra/pull/4951/files#diff-406185368ba7839d1459d3d51424f104)
    * Add trigger plugin to [prow/plugins.yaml](https://github.com/kubernetes/test-infra/pull/4951/files#diff-ae83e55ccb05896d5229df577d34255d)
    * Add test dashboards to [testgrid/config/config.yaml](https://github.com/kubernetes/test-infra/pull/4951/files#diff-49f154cd90facc43fda49a99885e6d17)
    * Modify [testgrid/jenkins_verify/jenkins_validat.go](https://github.com/kubernetes/test-infra/pull/4951/files#diff-7fb4731a02dd681bbd0daada8dd2f908)
       to allow presubmits for the new repo.
1. For tensorflow/k8s configure webhooks by following these [instructions](https://github.com/kubernetes/test-infra/blob/master/prow/getting_started.md#add-the-webhook-to-github)
    * Use https://prow.k8s.io/hook as the target
    * Get HMAC token from k8s test team
1. Add the k8s bot account, k8s-ci-robot, as an admin on the repository
    * Admin privileges are needed to update status (but not comment)
    * Someone with access to the bot will need to accept the request.
1. TODO(jlewi): Follow [instructions](https://github.com/kubernetes/test-infra/tree/master/gubernator#adding-a-repository-to-the-pr-dashboard) for adding a repository to the PR
   dashboard.