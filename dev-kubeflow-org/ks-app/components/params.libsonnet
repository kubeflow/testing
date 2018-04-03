{
  global: {
    // User-defined global parameters; accessible to all component and environments, Ex:
    // replicas: 4,
  },
  components: {
    // Component-level parameters, defined initially from 'ks prototype use ...'
    // Each object below should correspond to a component in the components/ directory
    "kubeflow-core": {
      cloud: "null",
      disks: "null",
      jupyterHubAuthenticator: "iap",
      jupyterHubImage: "gcr.io/kubeflow/jupyterhub-k8s:1.0.1",
      jupyterHubServiceType: "ClusterIP",
      name: "kubeflow-core",
      namespace: "null",
      reportUsage: "true",
      tfAmbassadorServiceType: "ClusterIP",
      tfDefaultImage: "null",
      tfJobImage: "gcr.io/kubeflow-images-staging/tf_operator:v20180329-a7511ff",
      tfJobUiServiceType: "ClusterIP",
      usageId: "f85740a3-5f60-4146-91b6-2ab7089cf01c",
    },
    "cert-manager": {
      acmeEmail: "google-kubeflow-team@google.com",
      acmeUrl: "https://acme-v01.api.letsencrypt.org/directory",
      name: "cert-manager",
      namespace: "null",
    },
    "iap-ingress": {
      clientID: "235037502967-9cpmvs4ljbiqb3ojtnhnhlkkd8d562rl.apps.googleusercontent.com",
      clientSecret: "eNyoA-ZtqC_HSSx95mGRPLR3",
      disableJwtChecking: "false",
      envoyImage: "gcr.io/kubeflow-images-staging/envoy:v20180309-0fb4886b463698702b6a08955045731903a18738",
      hostname: "dev.kubeflow.org",
      ipName: "kubeflow-tf-hub",
      issuer: "letsencrypt-prod",
      name: "iap-ingress",
      namespace: "kubeflow",
      secretName: "envoy-ingress-tls",
    },
  },
}
