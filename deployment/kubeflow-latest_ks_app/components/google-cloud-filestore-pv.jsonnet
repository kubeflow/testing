local env = std.extVar("__ksonnet/environments");
local params = std.extVar("__ksonnet/params").components["google-cloud-filestore-pv"];
[
  {
    apiVersion: "v1",
    kind: "PersistentVolume",
    metadata: {
      name: params.name,
      namespace: env.namespace,
    },
    spec: {
      capacity: {
        storage: params.storageCapacity,
      },
      accessModes: [
        "ReadWriteMany",
      ],
      nfs: {
        path: params.path,
        server: params.serverIP,
      },
    },
  },
  {
    apiVersion: "v1",
    kind: "PersistentVolumeClaim",
    metadata: {
      name: params.name,
      namespace: env.namespace,
    },
    spec: {
      accessModes: [
        "ReadWriteMany",
      ],
      storageClassName: "",
      resources: {
        requests: {
          storage: params.storageCapacity,
        },
      },
    },
  },
  // Set 777 permissions on the GCFS NFS so that non-root users
  // like jovyan can use that NFS share
  {
    apiVersion: "batch/v1",
    kind: "Job",
    metadata: {
      name: "set-gcfs-permissions",
      namespace: env.namespace,
    },
    spec: {
      template: {
        spec: {
          containers: [
            {
              name: "set-gcfs-permissions",
              image: "ubuntu",
              command: [
                "chmod",
                "777",
                "/kubeflow-gcfs",
              ],
              volumeMounts: [
                {
                  mountPath: "/kubeflow-gcfs",
                  name: params.name,
                },
              ],
            },
          ],
          restartPolicy: "OnFailure",
          volumes: [
            {
              name: params.name,
              persistentVolumeClaim: {
                claimName: params.name,
                readOnly: false,
              },
            },
          ],
        },
      },
    },
  },
]
