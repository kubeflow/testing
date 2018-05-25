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
      jupyterNotebookPVCMount: "null",
      name: "kubeflow-core",
      namespace: "null",
      reportUsage: "true",
      tfAmbassadorServiceType: "ClusterIP",
      tfDefaultImage: "null",
      tfJobImage: "gcr.io/kubeflow-images-public/tf_operator:v20180329-a7511ff",
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
      disableJwtChecking: "false",
      envoyImage: "gcr.io/kubeflow-images-public/envoy:v20180309-0fb4886b463698702b6a08955045731903a18738",
      hostname: "dev.kubeflow.org",
      ipName: "kubeflow-tf-hub",
      issuer: "letsencrypt-prod",
      name: "iap-ingress",
      namespace: "kubeflow",
      oauthSecretName: "kubeflow-oauth",
      secretName: "envoy-ingress-tls",
    },
    seldon: {
      apifeImage: "seldonio/apife:0.1.5",
      apifeServiceType: "NodePort",
      engineImage: "seldonio/engine:0.1.5",
      name: "seldon",
      namespace: "kubeflow",
      operatorImage: "seldonio/cluster-manager:0.1.5",
      operatorJavaOpts: "null",
      operatorSpringOpts: "null",
      withApife: "false",
      withRbac: "true",
    },
    "issue-summarization": {
      endpoint: "REST",
      image: "gcr.io/kubeflow-images-public/issue-summarization:0.1",
      name: "issue-summarization",
      namespace: "kubeflow",
      replicas: 1,
    },
    "issue-summarization-ui": {
      containerPort: 80,
      image: "gcr.io/kubeflow-images-public/issue-summarization-ui:latest",
      name: "issue-summarization-ui",
      namespace: "kubeflow",
      replicas: 1,
      servicePort: 80,
      // Need node port to expose it via ingress.
      type: "NodePort",
    },
  },
}
