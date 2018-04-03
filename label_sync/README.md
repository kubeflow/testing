# label_sync

kubeflow_label.yml: containing rules to update or migrate github labels on repos in kubeflow org
We use same tool from kubernetes: https://github.com/kubernetes/test-infra/tree/master/label_sync

Want to edit kubeflow_label.yml? Search process\_label.py (hacky) in this repo.

## Usage
```sh
# add or migrate labels on all repos in the kubeflow org
# Under kubernetes/test-infra/label_sync, run:
bazel run //label_sync -- \
  --config /path/to/kubeflow_label.yaml \
  --token /path/to/github_oauth_token \
  --orgs kubeflow
```