local env = std.extVar("__ksonnet/environments");
local params = std.extVar("__ksonnet/params").components.centraldashboard;
[
  {
    apiVersion: "extensions/v1beta1",
    kind: "Deployment",
    metadata: {
      labels: {
        app: "centraldashboard",
      },
      name: "centraldashboard",
      namespace: env.namespace,
    },
    spec: {
      template: {
        metadata: {
          labels: {
            app: "centraldashboard",
          },
        },
        spec: {
          containers: [
            {
              image: params.image,
              name: "centraldashboard",
              ports: [
                {
                  containerPort: 8082,
                },
              ],
            },
          ],
          serviceAccountName: "centraldashboard",
        },
      },
    },
  },  // deployUi

  {
    apiVersion: "v1",
    kind: "Service",
    metadata: {
      labels: {
        app: "centraldashboard",
      },
      name: "centraldashboard",
      namespace: env.namespace,
      annotations: {
        "getambassador.io/config":
          std.join("\n", [
            "---",
            "apiVersion: ambassador/v0",
            "kind:  Mapping",
            "name: centralui-mapping",
            "prefix: /",
            "rewrite: /",
            "service: centraldashboard." + env.namespace,
          ]),
      },  //annotations
    },
    spec: {
      ports: [
        {
          port: 80,
          targetPort: 8082,
        },
      ],
      selector: {
        app: "centraldashboard",
      },
      sessionAffinity: "None",
      type: "ClusterIP",
    },
  },  //service

  {
    apiVersion: "v1",
    kind: "ServiceAccount",
    metadata: {
      name: "centraldashboard",
      namespace: env.namespace,
    },
  },  // service account

  {
    apiVersion: "rbac.authorization.k8s.io/v1beta1",
    kind: "ClusterRole",
    metadata: {
      labels: {
        app: "centraldashboard",
      },
      name: "centraldashboard",
      namespace: env.namespace,
    },
    rules: [
      {
        apiGroups: [""],
        resources: [
          "pods",
          "pods/exec",
          "pods/log",
        ],
        verbs: [
          "get",
          "list",
          "watch",
        ],
      },
      {
        apiGroups: [""],
        resources: [
          "secrets",
        ],
        verbs: [
          "get",
        ],
      },
    ],
  },  // operator-role

  {
    apiVersion: "rbac.authorization.k8s.io/v1beta1",
    kind: "ClusterRoleBinding",
    metadata: {
      labels: {
        app: "centraldashboard",
      },
      name: "centraldashboard",
      namespace: env.namespace,
    },
    roleRef: {
      apiGroup: "rbac.authorization.k8s.io",
      kind: "ClusterRole",
      name: "centraldashboard",
    },
    subjects: [
      {
        kind: "ServiceAccount",
        name: "centraldashboard",
        namespace: env.namespace,
      },
    ],
  },  // role binding
]
