# K8s resources to cleanup test infrastructure

This directory contains K8s manifests to cleanup the Kubeflow CI.

Per [kubeflow/testing#654](https://github.com/kubeflow/testing/issues/654) we are
in the process of:

* Migrating from using K8s Jobs to using Tekton
* Using Kustomize as opposed to ksonnet
* Using GitOps(ACM) to keep the test infra up to date with the latest configs.

This directory contains a kustomize manifest for a cron-job to submit
a Tekton Pipeline to cleanup blueprint auto-deployments.

The PipelineRun in this directory can also be used for one-off manual runs of the cleanup
pipeline.