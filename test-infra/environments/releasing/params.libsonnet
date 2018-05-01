local params = import "../../components/params.libsonnet";
params {
  components+: {
    // Insert component parameter overrides here. Ex:
    // guestbook +: {
    //   name: "guestbook-dev",
    //   replicas: params.global.replicas,
    // },
    argo+: {
      namespace: "kubeflow-releasing",
    },
    "debug-worker"+: {
      namespace: "kubeflow-releasing",
      gcpCredentialsSecretName: "gcp-credentials",
    },
    "nfs-external"+: {
      namespace: "kubeflow-releasing",
      nfsServer: "10.128.0.4",
    },
  },
}
