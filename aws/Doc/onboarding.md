# Onboarding Process

This doc describes how to onboard new kubeflow repository using optional-test-infra

## Instructions
1. Grant repo write access to aws-kf-ci-bot, check [PR](https://github.com/kubeflow/internal-acls/pull/373)
2. Configure Prow
    * Add Prow Jobs to [prow/config.yaml](https://github.com/kubeflow/testing/blob/master/aws/User/clusters/optional-shared-test-infra-prow/namespaces/prow/configmap/config.yaml)
    * Add trigger plugin to [prow/plugins.yaml](https://github.com/kubeflow/testing/blob/master/aws/User/clusters/optional-test-infra-prow/namespaces/prow/configmap/plugins.yaml)
