# Kubeflow deployment

This directory contains kfctl apps corresponding to Kubeflow deployments.

These deployments are used for running tests against specific versions of Kubeflow.
For example, there should be an app for each major release, X.Y, of Kubeflow.
E2E tests for the Kubeflow examples can run against these deployments in order to ensure
they work on a particular version of Kubeflow.

## Creating a Kubeflow deployment

To upgrade the deployment.

1. Run `upgrade_app.sh latest|stable`

1. Run `redeploy_app.sh latest|stable`

## Istio setup

TODO(jlewi/llunn): I think this section needs to be updated.

We use istio to get metrics for TF Serving services, see [doc](https://github.com/kubeflow/kubeflow/blob/master/components/k8s-model-server/istio-integration.md).
- Follow the istio [doc](https://istio.io/docs/setup/kubernetes/quick-start.html#installation-steps) to install istio. 
- Install prometheus and grafana [addons](https://istio.io/docs/tasks/telemetry/using-istio-dashboard.html).
- Follow [doc](https://github.com/kubeflow/kubeflow/blob/master/components/k8s-model-server/istio-integration.md#install-and-configure-istio-sidecar-injector) to install auto injector. This requires Kubernetes 1.9 or above.

Finally, label the namespace of kubeflow deployment:
```
kubectl label namespace ${NAMESPACE} istio-injection=enabled
```
