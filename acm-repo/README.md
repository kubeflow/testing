# Anthos Configuration Management Directory

This is the root directory for Anthos Configuration Management.

See [our documentation](https://cloud.google.com/anthos-config-management/docs/repo) for how to use each subdirectory.

* TODO(jlewi): We should have a single ACM repo for all KF CI/CD related clusters
  * I think we want a single ACM repo for all KF ci infrastructure. We can then use
    [cluster selectors](https://cloud.google.com/anthos-config-management/docs/how-to/clusterselectors)
    to limit clusters it appliies to.
* TODO(jlewi): We should move the [label-sync repo](https://github.com/kubeflow/testing/tree/master/label_sync/acm_repo)
  into this directory and then use cluster selectors to limit clusters it applies to.