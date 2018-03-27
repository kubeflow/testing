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
      exposeUi: false,
    },
    "nfs-external": {
      name: "nfs-external",
      namespace: "kubeflow-test-infra",
      nfsServer: "10.142.0.6",
    },
    "debug-worker": {
      name: "debug-worker",
      namespace: "kubeflow-test-infra",
      gcpCredentialsSecretName: "kubeflow-testing-credentials",
    },
  },
}
