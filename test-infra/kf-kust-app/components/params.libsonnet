{
  global: {
    // User-defined global parameters; accessible to all component and environments, Ex:
    // replicas: 4,
  },
  components: {
    // Component-level parameters, defined initially from 'ks prototype use ...'
    // Each object below should correspond to a component in the components/ directory
    argo: {
      namespace: "kubeflow-test-infra",
      imageUi: "argoproj/argoui:v2.2.1-37808b1",
      image: "argoproj/workflow-controller:v2.2.1",
      version: "v2.2.1",
      exposeUi: false,
    },
    "cleanup-ci": {
      name: "cleanup-ci",
    },
    "cleanup-ci-cron": {
      name: "cleanup-ci",
    },
    "nfs-external": {
      name: "nfs-external",
      namespace: "kubeflow-test-infra",
      nfsServer: "",
    },
    "debug-worker": {
      name: "debug-worker",
      namespace: "kubeflow-test-infra",
      gcpCredentialsSecretName: "kubeflow-testing-credentials",
    },
  },
}
