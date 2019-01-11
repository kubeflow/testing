// This component defines a stateful set that just starts a pod using the same image
// as the workers used by our Argo workflows and mounts the same NFS volumes.
// This is useful for looking at the files because you can just do kubectl exec.
local params = std.extVar("__ksonnet/params").components["debug-worker"];
// TODO(https://github.com/ksonnet/ksonnet/issues/222): We have to add namespace as an explicit parameter
// because ksonnet doesn't support inheriting it from the environment yet.

local k = import "k.libsonnet";

local name = params.name;
local namespace = params.namespace;


local ss = {
  apiVersion: "apps/v1beta1",
  kind: "StatefulSet",
  metadata: {
    name: "debug-worker",
    namespace: namespace,
  },
  spec: {
    replicas: 1,
    serviceName: "",
    template: {
      metadata: {
        labels: {
          app: "debug-worker",
        },
      },
      spec: {
        containers: [
          {
            command: [
              "tail",
              "-f",
              "/dev/null",
            ],
            env: [
              {
                name: "GOOGLE_APPLICATION_CREDENTIALS",
                value: "/secret/gcp-credentials/key.json",
              },
            ],
            image: "gcr.io/kubeflow-ci/test-worker:latest",
            name: "test-container",
            volumeMounts: [
              {
                mountPath: "/mnt/test-data-volume",
                name: "nfs-external",
              },
              {
                mountPath: "/secret/gcp-credentials",
                name: "gcp-credentials",
              },
            ],
          },
        ],
        volumes: [
          {
            name: "nfs-external",
            persistentVolumeClaim: {
              claimName: "nfs-external",
            },
          },
          {
            name: "gcp-credentials",
            secret: {
              secretName: params.gcpCredentialsSecretName,
            },
          },
        ],

      },
    },
    updateStrategy: {
      type: "RollingUpdate",
    },
  },
};

std.prune(k.core.v1.list.new([
  ss,
]))
