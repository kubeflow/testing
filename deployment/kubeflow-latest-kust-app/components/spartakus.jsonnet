local env = std.extVar("__ksonnet/environments");
local params = std.extVar("__ksonnet/params").components.spartakus;

local util = import "kubeflow/core/util.libsonnet";
local reportUsageBool = util.toBool(params.reportUsage);

if reportUsageBool then [
  // Spartakus needs to be able to get information about the cluster in order to create a report.
  {
    apiVersion: "rbac.authorization.k8s.io/v1beta1",
    kind: "ClusterRole",
    metadata: {
      labels: {
        app: "spartakus",
      },
      name: "spartakus",
    },
    rules: [
      {
        apiGroups: [
          "",
        ],
        resources: [
          "nodes",
        ],
        verbs: [
          "get",
          "list",
        ],
      },
    ],
  },  // role

  {
    apiVersion: "rbac.authorization.k8s.io/v1beta1",
    kind: "ClusterRoleBinding",
    metadata: {
      labels: {
        app: "spartakus",
      },
      name: "spartakus",
    },
    roleRef: {
      apiGroup: "rbac.authorization.k8s.io",
      kind: "ClusterRole",
      name: "spartakus",
    },
    subjects: [
      {
        kind: "ServiceAccount",
        name: "spartakus",
        namespace: env.namespace,
      },
    ],
  },  // operator-role binding

  {
    apiVersion: "v1",
    kind: "ServiceAccount",
    metadata: {
      labels: {
        app: "spartakus",
      },
      name: "spartakus",
      namespace: env.namespace,
    },
  },

  {
    apiVersion: "extensions/v1beta1",
    kind: "Deployment",
    metadata: {
      name: "spartakus-volunteer",
      namespace: env.namespace,
    },
    spec: {
      replicas: 1,
      template: {
        metadata: {
          labels: {
            app: "spartakus-volunteer",
          },
        },
        spec: {
          containers: [
            {
              image: "gcr.io/google_containers/spartakus-amd64:v1.0.0",
              name: "volunteer",
              args: [
                "volunteer",
                "--cluster-id=" + params.usageId,
                "--database=https://stats-collector.kubeflow.org",
              ],
            },
          ],
          serviceAccountName: "spartakus",
        },  // spec
      },
    },
  },  // deployment
] else []
