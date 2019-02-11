# label_sync

kubeflow_label.yml: containing rules to update or migrate github labels on repos in kubeflow org
We use same tool from kubernetes: https://github.com/kubernetes/test-infra/tree/master/label_sync

Want to edit kubeflow_label.yml? Take a look at [process_label.py](../hack/label_generate/process_label.py).

## Usage
```sh
# add or migrate labels on all repos in the kubeflow org
# Under kubernetes/test-infra/label_sync, run:
bazel run //label_sync -- \
  --config /path/to/kubeflow_label.yaml \
  --token /path/to/github_oauth_token \
  --orgs kubeflow
```

## Cron Job

We currently run a cron job synchronize labels in

  * **Project**: kubeflow-admin
  * **Cluster**: kf-admin-cluster
  * **Namespace**: github-admin

We use a separate cluster in a restricted project because modifying the labels requires write permission on all repos.

We have a CronJob to sync the labels, defined
[here](https://github.com/kubeflow/testing/blob/master/label_sync/cluster/label_sync_job.yaml).
After making changes to `kubeflow_label.yml`, we need to update the configmap
[label-config-v2](https://github.com/kubeflow/testing/blob/master/label_sync/cluster/label_sync_job.yaml#L37):
```
# Setup kubectl to point to kubeflow-testing cluster in kubeflow-ci
kubectl -n github-admin delete configmap label-config-v2
kubectl -n github-admin create configmap label-config-v2 --from-file=kubeflow_label.yml
```
### Create a GitHub OAuth token

Use GitHub to create an OAuth token
 
  * You need repo scope in order to modify labels on issues


```
kubectl -n github-admin create secret generic bot-token-github --from-literal=bot-token=${GITHUB_TOKEN}
```
## Create the cron job

```
kubectl -n github-admin apply -f cluster/label_sync_cron_job.yaml
```