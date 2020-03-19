# label_sync

kubeflow_label.yml: containing rules to update or migrate github labels on repos in kubeflow org
We use same tool from kubernetes: https://github.com/kubernetes/test-infra/tree/master/label_sync

## How to add or rename labels

1. Modify kubeflow_label.yml

   * Define new labels or add entries to rename labels

1. Run

   ```
   hydrate.sh
   ```

   * This will run `kustomize build` to generate an updated configmap and update the cronjob to use the new config
   * The hydrated manifests are written to the directory `acm_repo`

1. Create a PR with the changes


1. After the next succesful run of the cron job your changes should be applied to all repos.


## How it works

### Label sync binary

[label_sync](https://github.com/kubernetes/test-infra/tree/master/label_sync) is a binary produced by the Kubernetes test infra
team to sync labels in GitHub based on a YAML config file.

Here's an example invocation of that binary


```sh
# add or migrate labels on all repos in the kubeflow org
# Under kubernetes/test-infra/label_sync, run:
bazel run //label_sync -- \
  --config /path/to/kubeflow_label.yaml \
  --token /path/to/github_oauth_token \
  --orgs kubeflow
```

### Cron Job

We use a Kubernetes cron job to periodically run label_sync.

We currently run a cron job synchronize labels in

  * **Project**: kubeflow-admin
  * **Cluster**: kf-admin-cluster
  * **Namespace**: github-admin

We use a separate cluster in a restricted project because modifying the labels requires write permission on all repos.

We have a CronJob to sync the labels, defined
[here](https://github.com/kubeflow/testing/blob/master/label_sync/cluster/label_sync_job.yaml).

### ACM to sync Kubernetes Resources

We use Anthos Config Management(ACM) to continually sync changes to the kubernetes resources to the kubernetes cluster.

Right now the user has to manually run `hydrate.sh` to generate hydrated manifests that get checked in as part of the PR.


### GitHub OAuth token

The label_sync binary depends on a GitHub OAuth token which is stored as a configmap. (We would like to change this to a GitHub App)

Use GitHub to create an OAuth token
 
  * You need repo scope in order to modify labels on issues


```
kubectl -n github-admin create secret generic bot-token-github --from-literal=bot-token=${GITHUB_TOKEN}
```
