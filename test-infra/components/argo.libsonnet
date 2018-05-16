{
  parts(namespace, version):: {
    crd: {
      apiVersion: "apiextensions.k8s.io/v1beta1",
      kind: "CustomResourceDefinition",
      metadata: {
        name: "workflows.argoproj.io",
      },
      spec: {
        group: "argoproj.io",
        version: "v1alpha1",
        scope: "Namespaced",
        names: {
          kind: "Workflow",
          plural: "workflows",
          shortNames: [
            "wf",
          ],
        },
      },
    },  // crd

    argoServiceAccount: {
      apiVersion: "v1",
      kind: "ServiceAccount",
      metadata: {
        name: "argo",
        namespace: namespace,
      },
    },

    argoClusterRole: {
      apiVersion: "rbac.authorization.k8s.io/v1",
      kind: "ClusterRole",
      metadata: {
        name: "argo-cluster-role",
      },
      rules: [
        {
          apiGroups: [
            "",
          ],
          resources: [
            "pods",
            "pods/exec",
          ],
          verbs: [
            "create",
            "get",
            "list",
            "watch",
            "update",
            "patch",
          ],
        },
        {
          apiGroups: [
            "",
          ],
          resources: [
            "configmaps",
          ],
          verbs: [
            "get",
            "watch",
            "list",
          ],
        },
        {
          apiGroups: [
            "",
          ],
          resources: [
            "persistentvolumeclaims",
          ],
          verbs: [
            "create",
            "delete",
          ],
        },
        {
          apiGroups: [
            "argoproj.io",
          ],
          resources: [
            "workflows",
          ],
          verbs: [
            "get",
            "list",
            "watch",
            "update",
            "patch",
          ],
        },
      ],
    },  // argoClusterRole

    argoClusterRoleBinding: {
      apiVersion: "rbac.authorization.k8s.io/v1",
      kind: "ClusterRoleBinding",
      metadata: {
        name: "argo-binding",
      },
      roleRef: {
        apiGroup: "rbac.authorization.k8s.io",
        kind: "ClusterRole",
        name: "argo-cluster-role",
      },
      subjects: [
        {
          kind: "ServiceAccount",
          name: "argo",
          namespace: namespace,
        },
      ],
    },

    argoConfigMap: {
      apiVersion: "v1",
      kind: "ConfigMap",
      metadata: {
        name: "workflow-controller-configmap",
        namespace: namespace,
      },
      data: {
        config: "artifactRepository: {}\nexecutorImage: argoproj/argoexec:" + version + "\n",
      },
    },

    argoDeployment: {
      apiVersion: "apps/v1beta2",
      kind: "Deployment",
      metadata: {
        name: "workflow-controller",
        namespace: namespace,
      },
      spec: {
        selector: {
          matchLabels: {
            app: "workflow-controller",
          },
        },
        template: {
          metadata: {
            labels: {
              app: "workflow-controller",
            },
          },
          spec: {
            serviceAccountName: "argo",
            containers: [
              {
                name: "workflow-controller",
                image: "argoproj/workflow-controller:" + version,
                command: [
                  "workflow-controller",
                ],
                args: [
                  "--configmap",
                  "workflow-controller-configmap",
                ],
                env: [
                  {
                    name: "ARGO_NAMESPACE",
                    valueFrom: {
                      fieldRef: {
                        apiVersion: "v1",
                        fieldPath: "metadata.namespace",
                      },
                    },
                  },
                ],
              },
            ],
          },
        },
      },
    },  // argoDeployment

    argoUiServiceAccount: {
      apiVersion: "v1",
      kind: "ServiceAccount",
      metadata: {
        name: "argo-ui",
        namespace: namespace,
      },
    },

    argoUiClusterRole: {
      apiVersion: "rbac.authorization.k8s.io/v1",
      kind: "ClusterRole",
      metadata: {
        name: "argo-ui-cluster-role",
      },
      rules: [
        {
          apiGroups: [
            "",
          ],
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
          apiGroups: [
            "",
          ],
          resources: [
            "secrets",
          ],
          verbs: [
            "get",
          ],
        },
        {
          apiGroups: [
            "argoproj.io",
          ],
          resources: [
            "workflows",
          ],
          verbs: [
            "get",
            "list",
            "watch",
          ],
        },
      ],
    },  // argoUiClusterRole

    argoUiClusterRoleBinding: {
      apiVersion: "rbac.authorization.k8s.io/v1",
      kind: "ClusterRoleBinding",
      metadata: {
        name: "argo-ui-binding",
      },
      roleRef: {
        apiGroup: "rbac.authorization.k8s.io",
        kind: "ClusterRole",
        name: "argo-ui-cluster-role",
      },
      subjects: [
        {
          kind: "ServiceAccount",
          name: "argo-ui",
          namespace: namespace,
        },
      ],
    },

    argoUiDeployment: {
      apiVersion: "apps/v1beta2",
      kind: "Deployment",
      metadata: {
        name: "argo-ui",
        namespace: namespace,
      },
      spec: {
        selector: {
          matchLabels: {
            app: "argo-ui",
          },
        },
        template: {
          metadata: {
            labels: {
              app: "argo-ui",
            },
          },
          spec: {
            serviceAccountName: "argo-ui",
            containers: [
              {
                name: "argo-ui",
                image: "argoproj/argoui:" + version,
                env: [
                  {
                    name: "ARGO_NAMESPACE",
                    valueFrom: {
                      fieldRef: {
                        apiVersion: "v1",
                        fieldPath: "metadata.namespace",
                      },
                    },
                  },
                  {
                    name: "IN_CLUSTER",
                    value: "true",
                  },
                  {
                    name: "ENABLE_WEB_CONSOLE",
                    value: "false",
                  },
                  {
                    name: "BASE_HREF",
                    value: "/",
                  },
                ],
              },
            ],
          },
        },
      },
    },  // argoUiDeployment

    argoUiService: {
      apiVersion: "v1",
      kind: "Service",
      metadata: {
        name: "argo-ui",
        namespace: namespace,
      },
      spec: {
        ports: [
          {
            port: 80,
            targetPort: 8001,
          },
        ],
        selector: {
          app: "argo-ui",
        },
        sessionAffinity: "None",
        type: "NodePort",
      },
    },

    uiIngress: {
      apiVersion: "extensions/v1beta1",
      kind: "Ingress",
      metadata: {
        name: "argo-ui",
        namespace: namespace,
        annotations: {
          "kubernetes.io/ingress.global-static-ip-name": "argo-ui",
        },
      },
      spec: {
        backend: {
          serviceName: "argo-ui",
          servicePort: 80,
        },
      },
    },  // uiIngress

  },
}
