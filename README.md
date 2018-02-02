# Test Infrastructure

This directory contains the Kubeflow test Infrastructure.

This is a work in progress see [kubeflow/kubeflow#38](https://github.com/kubeflow/kubeflow/issues/38)

The current thinking is this will work as follows

  * Prow will be used to trigger E2E tests
  * The E2E test will launch an Argo workflow that describes the tests to run
  * Each step in the Argo workflow will be a binary invoked inside a container
  * The Argo workflow will use an NFS volume to attach a shared POSIX compliant filesystem to each step in the
    workflow.
  * Each step in the pipeline can write outputs and junit.xml files to a test directory in the volume
  * A final step in the Argo pipeline will upload the outputs to GCS so they are available in gubernator

## Accessing Argo UI

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