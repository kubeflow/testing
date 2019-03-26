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