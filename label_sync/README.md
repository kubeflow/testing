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