# Kubeflow deployment

ksonnet app for the kubeflow deployment at dev.kubeflow.org

## Upgrading

To upgrade the deployment.

1. modify `recreate_app.sh` and set the VERSION to the kubeflow RC
   to deploy.

1. Run `recreate_app.sh`

1. Run `redeploy_app.sh`

# Istio setup

We use istio to get metrics for TF Serving services, see [doc](https://github.com/kubeflow/kubeflow/blob/master/components/k8s-model-server/istio-integration.md).
- Follow the istio [doc](https://istio.io/docs/setup/kubernetes/quick-start.html#installation-steps) to install istio. 
- Install prometheus and grafana [addons](https://istio.io/docs/tasks/telemetry/using-istio-dashboard.html).
- Follow [doc](https://github.com/kubeflow/kubeflow/blob/master/components/k8s-model-server/istio-integration.md#install-and-configure-istio-sidecar-injector) to install auto injector. This requires Kubernetes 1.9 or above.

Finally, label the namespace of kubeflow deployment:
```
kubectl label namespace ${NAMESPACE} istio-injection=enabled
```