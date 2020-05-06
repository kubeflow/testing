# Kubeflow Tekton Catalog

This directory contains a catalog of Tekton tasks related to Kubeflow.

Some of these tasks are for Kubeflow CI/CD.


TODO(jlewi):
 
  * We need to figure out the deployment and GitOps story
  * My initial thought is this directory should contain unhydrated manifests.
  * Manifests should be hydrated using kustomize and kpt 
  * The hydrated manifests should then be deployed using ACM or similar tools.
  * I think we want a single ACM repo for all KF ci infrastructure. We can then use
    [cluster selectors](https://cloud.google.com/anthos-config-management/docs/how-to/clusterselectors)
    to limit clusters it appliies to.