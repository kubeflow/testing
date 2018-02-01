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
    },
    "nfs-jupyter": {
      cloud: "",
      disks: "kubeflow-testing",
      name: "nfs-jupyter",
      namespace: "kubeflow-test-infra",
      tfJobImage: "gcr.io/tf-on-k8s-dogfood/tf_operator:v20171214-0bd02ac",
    },
    "nfs-external": {
      name: "nfs-external",
      namespace: "kubeflow-test-infra",
      nfsServer: "10.142.0.6",
    },
  },
}
