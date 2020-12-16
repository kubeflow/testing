# Onboarding Process

This doc describes how to onboard new kubeflow repository using optional-test-infra

## Preparations
1. Grant repo access to aws-kf-ci-bot, check [PR](https://github.com/kubeflow/internal-acls/pull/373)
2. Add Webhook to the repo, ping YaoXiao@ for help
3. Configure Presubmit on Optional-Test-Infra Prow Cluster, check [PR](https://github.com/kubeflow/internal-acls/pull/373)

## Instructions 
A geneic Argo Workflow / Tekton Pipelinerun diagram attached [here](https://github.com/kubeflow/testing/tree/master/aws/Picture/GenericArgoWorkflow.png)

Below is the steps for WG who want to write a simple E2E test cases

1. setup_cluster or tear_down cluster. You can remove all GCP settings and use [these scripts](https://github.com/kubeflow/testing/tree/master/images/aws-scripts) instead, scripts have been built into the test image.
   <br> If you need GPU instances, feel free to check [here](https://github.com/kubeflow/testing/blob/master/images/aws-scripts/create-eks-cluster.sh#L32) to pass P3.2xlarge as instance type. (I would recommend not using GPU for now)
2. We need to change the intermediate image to use ECR, we use Kaniko to build images. check [here](https://github.com/kubeflow/pytorch-operator/blob/master/test/workflows/components/workflows.libsonnet#L328-L340) for more details. You can stick with Bash scripts or other tools.
WG folks should provide a list of ECR registries they want to use, Ping Yao Xiao@ as well.
3. Remove all GCP credentials mounts and add aws mounts, REGION instead. For more details, please check [PR](https://github.com/kubeflow/pytorch-operator/pull/305)
4. For existing shells which fetch GKE credentials, you can remove all of them and use AWS one by following [this](https://github.com/kubeflow/pytorch-operator/pull/305/files#diff-d99e924ca9f84f28b6c4decf07cee8a86513c5852272b05512dca7081d3e9e75R158-R159)

## Applying for Access to Optional-Test-Infra
WG TechLeads can also follow [this doc](https://docs.google.com/document/d/1hrjIDO7UQ8l5uvADSxbiyM2GDfst1L7vyIKekrrdlwA/edit) to ask for Editor/Viewer Permissions to Optional-Test-infra DataPlane.


