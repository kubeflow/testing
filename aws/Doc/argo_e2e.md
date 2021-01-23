# Writing Argo workflow for E2E Test

A generic Argo Workflow diagram attached [here](https://github.com/kubeflow/testing/tree/master/aws/Picture/GenericArgoWorkflow.png)

Below are the steps for WG who want to write a generic E2E test cases

1. setup_cluster or tear_down cluster. You can remove all GCP settings and use [these scripts](https://github.com/kubeflow/testing/tree/master/images/aws-scripts) instead, scripts have been built into the test image.
2. We need to change the intermediate testing image to use ECR, we use Kaniko to build images. check [here](https://github.com/kubeflow/pytorch-operator/blob/master/test/workflows/components/workflows.libsonnet#L328-L340) for more details. You can stick with Bash scripts or other tools.
WG folks should provide a list of ECR registries they want to use, Ping Yao Xiao@ as well.
3. Remove all GCP credentials mounts and add aws credentials, REGION instead. For more details, please check [PR](https://github.com/kubeflow/pytorch-operator/pull/305/files#diff-d99e924ca9f84f28b6c4decf07cee8a86513c5852272b05512dca7081d3e9e75R194-R198)
4. For existing shells which fetch GKE credentials, you can remove all of them and use AWS one by following [this](https://github.com/kubeflow/pytorch-operator/pull/305/files#diff-d99e924ca9f84f28b6c4decf07cee8a86513c5852272b05512dca7081d3e9e75R158-R159)
