# User Modifiable Files

This folder includes all the files that can be modified by users, the file organization is described as below:

```
clusters
  - A cluster
    - namespaces
      - a namespace
        - CRD / Standard K8s Objects
          - d CRD
          - e CRD
          ...
      - b namespace
      ...
  - B cluster
  ...
```

## Add Prow jobs in Optional-Test-Infra
Add specific prows jobs in [config.yaml](https://github.com/kubeflow/testing/tree/master/aws/User/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/configmap/config.yaml) file

## Add Argo Resources in Argo cluster
Add expected yaml files in [argo folder](https://github.com/kubeflow/testing/tree/master/aws/User/clusters/kubeflow-shared-test-infra-poc-argo/namespaces/argo/)

## Add Tekton Resources in Tekton cluster
Add expected yaml files in [tekton folder](https://github.com/kubeflow/testing/tree/master/aws/User/clusters/kubeflow-shared-test-infra-poc-tekton/namespaces/tekton-templates/)

Note: any change you make in this folder, please run `make optional-generate` to generate files in GitOps folder before sending PR
