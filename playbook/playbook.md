# Kubeflow Test Infrastructure Playbook

This is a playbook for build cops to help deal with problems with the CI infrastructure.


## GCP Quota errors

1. There is a stack driver dashboard named [CI Health](https://console.cloud.google.com/monitoring/dashboards/custom/11734777947337404240?project=kubeflow-ci-deployment&timeDomain=1w) that can be used to check various quota usages like CPUs

1. List regional quotas to see which quotas are running hot

   ```
   gcloud compute regions describe --project=kubeflow-ci ${REGION}
   ```

1. Check if we are leaking Kubeflow deployments and this is causing us to run out of quota.

   ```
   gcloud --project=kubeflow-ci --format="table(name,createTime:sort=1,location,status)" container clusters list
   gcloud --project=kubeflow-ci deployment-manager deployments list --format="table(name,insertTime:sort=1)" 
   ```

   * Deployments created by the E2E tests should be GC'd after O(2) hours
   * So if there are resources older than O(2) hours it indicates that there is a problem with
     garbage collection

1. To access to k8s resources make sure to get credentials and set the default namespace to `kubeflow-test-infra`:

```
gcloud --project kubelow-ci container clusters get-credentials kubeflow-testing --zone $ZONE
kubectl config set-context $(kubectl config current-context) --namespace=kubeflow-test-infra
```

1. Check if the cron job to GC resources is running in the test cluster

   ```
   kubectl get cronjobs
   NAME                 SCHEDULE       SUSPEND   ACTIVE    LAST SCHEDULE   AGE	
   cleanup-ci           0 */2 * * *    False     0         <none>          14m
   ```

   * The cron job is defined in [cleanup-ci-cron.jsonnet](https://github.com/kubeflow/testing/blob/master/test-infra/ks_app/components/cleanup-ci-cron.jsonnet)

   * If the cron job is not configured then start it.


1. Look for recent runs of the cron job and figure out whether the are running successfully

   ```
    kubectl get jobs -l app=cleanup-ci-kubeflow-ci-deployment --sort-by=".metadata.creationTimestamp"
   ```

   * Jobs triggered by cron will match the regex `cleanup-ci-??????????`

   * Check that the job ran successfully

   * The pods associated with the job can be fetched via labels

     ```
     kubectl logs -l job-name=${JOBNAME}
     ```

   * In [stackdriver](https://console.cloud.google.com/logs/viewer?interval=PT1H&project=kubeflow-ci&minLogLevel=0&expandAll=false&advancedFilter=resource.type%3D%22k8s_container%22%0Aresource.labels.project_id%3D%22kubeflow-ci%22%0Aresource.labels.cluster_name%3D%22kubeflow-testing%22%0Alabels.%22k8s-pod%2Fjob-name%22%3D%22cleanup-ci-kubeflow-ci-deployment-1586916000%22%0A) you can use the following query (change the value of job-name)

     ```
     resource.type="k8s_container"
     resource.labels.project_id="kubeflow-ci"
     resource.labels.cluster_name="kubeflow-testing"
     labels."k8s-pod/job-name"="cleanup-ci-kubeflow-ci-deployment-1586916000"
     ```

1. Do a oneoff run of the cleanup job

   ```
   cd test-infra
   kubectl create -f cleanup-ci-kubeflow-ci-deployment.yaml
   ```

   * You can adjust the command line arguments in order to do more aggressive garbage collection then usual

## GCP SSL Certificate Quota Errors

This is a helpful command to list SSL certificates and their associated domain

```
gcloud beta --project=kubeflow-ci-deployment compute ssl-certificates list  --format="table(name,managed.domains,creationTimestamp:sort=1)"
```

## GCP Stockouts

1. Find a region with available quota

   ```
   gcloud --project=kubeflow-ci-deployment compute regions describe ${REGION}
   ```

   * We currently have quota in us-east1 and us-central1

1. Change the kfctl tests to use the other zone

   * Currently this is hardcoded in python in [kfctl_go_test_utils.py](https://github.com/kubeflow/kfctl/blob/c5c55f6d1b79e285f28fa433d6e4e2e739cefb63/py/kubeflow/kfctl/testing/util/kfctl_go_test_utils.py#L247)


## NFS Volume Is Out Of Disk Space.

1. Use [stackdriver](https://cloud.google.com/filestore/docs/monitoring-instances)
   to check the disk usage

   * TODO(jlewi): We should add this to the [Kubeflow CI Health Dashboard](https://console.cloud.google.com/monitoring/dashboards/custom/11734777947337404240?project=kubeflow-ci-deployment&timeDomain=1w)

1. There are two ways to free up disk space

   1. Delete old directories on the NFS share

   1. Delete and recreate the NFS share

   * Both options are outlined below

### Deleting old directories on the NFS share

1. Start a shell in the [debug worker](https://github.com/kubeflow/testing/blob/master/test-infra/ks_app/components/debug-worker.jsonnet)

   ```
   kubectl exec -it debug-worker-0 /bin/bash
   ```

1. Delete old directories

   ```
   cd /mnt/test-data-volume
   find -maxdepth 1 -type d ! -path . -mtime +7 -exec rm -rf {} ";"
   ```

### Deleting and recreating the NFS share

1. Delete the PV and pvc

   ```
   kubectl delete pvc nfs-external
   kubectl delete pv gcfs   
   kubectl delete pods --all=true
   ```

   * We delete the pods since the pods will be mounting the volume which will prevent deletion of the PV and PVC

1. Wait for them to be deleted

   * Most likely we will need to override [delete protection](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#storage-object-in-use-protection) because there will be some pods still mounting it


   * Dump the yaml
    
     ```
     kubectl  get pvc nfs-external -o yaml > /tmp/nfs-external.yaml
     ```

   * Delete the finalizer `kubernetes.io/pvc-protection` in nfs-external.yaml

     ```
     ...
     finalizers:
     labels:
     ...
     ```

     * Make sure you have the field finalizers and its an empty list

   * Update the object

     ```
     kubectl apply -f /tmp/nfs-external.yaml
     ```
     * Alternatively you can use `kubectl edit` to remove finalizers.	
   
   * Similarly, make sure you remove finzlizers from pv (i.e.,  gcfs)

1. If pv/pvc deleteion still stalls, delete all pods in `kubeflow-test-infra`  manually
   
 	```
	kubectl delete pods --all
  	```


1. Delete the nfs deployment

   ```
   gcloud --project=kubeflow-ci deployment-manager deployments delete kubeflow-ci-nfs
   ```

1. Recreate the NFS share

   ```
   cd test-infra/gcp_configs
   gcloud --project=kubeflow-ci deployment-manager deployments create kubeflow-ci-nfs --config=gcfs.yaml
   ```

1. Get the IP address of the new NFS share

   ```
   gcloud beta --project=kubeflow-ci filestore instances list
   ```

1. Set the IP address in the PV

   * Edit `test-infra/base/pvc.yaml`
   * Change the server address of the persistent volume to the new PV   

1. Recreate the PV and PVC

   ```
   cd test-infra/
   kustomize build base | kubectl apply -f -
   ```

1. Make sure the `debug-worker-0` pod is able to successfully mount the PV

  * You may need to restart the debug worker if it isn't running

     ```
     ks apply kubeflow-ci -c debug-worker
     ```
	
	* If you already deleted the pod `debug-worker-0` make sure it is restarted and is healthy. Otherwise, if it stalls in terminated state, force delete it as follows:

	```
	kubectl delete pods debug-worker-0 --grace-period=0 --force
	```
	
	* Connect to `debug-worker-0` to make sure it is able to mount the PV

	```
	kubectl exec -it debug-worker-0 /bin/bash
	ls /secret
	```
