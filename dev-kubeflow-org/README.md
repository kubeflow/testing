ksonnet app for the kubeflow deployment at dev.kubeflow.org

## Upgrading

To upgrade the deployment.

1. modify `recreate_app.sh` and set the VERSION to the kubeflow RC
   to deploy.

1. Run `recreate_app.sh`

1. Run `redeploy.sh`