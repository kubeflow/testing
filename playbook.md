# Kubeflow Test Infrastructure Playbook

This is a playbook for build cops to help deal with problems with the CI infrastructure.


## GCP Quota errors

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
   kubectl get jobs | grep cleanup-ci
   ```

   * Jobs triggered by cron will match the regex `cleanup-ci-??????????`

   * Check that the job ran successfully

   * The pods associated with the job can be fetched via labels

     ```
     kubectl logs -l job-name=${JOBNAME}
     ```

## NFS Volume Is Out Of Disk Space.

1. Use [stackdriver](https://cloud.google.com/filestore/docs/monitoring-instances)
   to check the disk usage

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

1. Delete the nfs deployment

   ```
   gcloud --project=kubeflow-ci deployment-manager delete kubeflow-ci-nfs
   ```

1. Delete the PV and pvc

   ```
   kubectl delete pv gcfs
   kubectl delete pvc gcfs-storage 
   ```

1. Wait for them to be deleted

   * Most likely we will need to override [delete protection](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#storage-object-in-use-protection) because there will be some pods still mounting it


   * Dump the yaml
    
     ```
     kubectl get pvc nfs-external -o yaml > /tmp/nfs-external.yaml
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

1. Rereate the NFS share

   ```
   cd test-infra/gcp_configs
   gcloud --project=kubeflow-ci deployment-manager deployments create kubeflow-ci-nfs --config=gcfs.yaml
   ```

1. Get the IP address of the new NFS share

   ```
   gcloud beta --project=kubeflow-ci filestore instances list
   ```

1. Set the IP address in the PV

   ```
   cd test-infra/ks_app
   ks param set --env=kubeflow-ci nfs-external nfsServer 10.240.92.210
   ```

1. Recreate the PV and PVC

   ```
   ks apply kubeflow-ci -c nfs-external
   ```

1. Make sure the `debug-worker-0` pod is able to successfully mount the PV