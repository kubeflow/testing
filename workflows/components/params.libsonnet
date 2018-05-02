{
  global: {
    // User-defined global parameters; accessible to all component and environments, Ex:
    // replicas: 4,
  },
  components: {
    // Component-level parameters, defined initially from 'ks prototype use ...'
    // Each object below should correspond to a component in the components/ directory
    workflows: {
      bucket: "kubeflow-ci_temp",
      name: "jlewi-kubeflow-test-presubmit-test-33-a3bc",
      namespace: "kubeflow-test-infra",
      prow_env: "JOB_NAME=kubeflow-test-presubmit-test,JOB_TYPE=presubmit,PULL_NUMBER=33,REPO_NAME=testing,REPO_OWNER=kubeflow,BUILD_NUMBER=a3bc",
    },
  },
}
