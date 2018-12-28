// This component defines persistent volumes and claims for an external
// NFS file system.
local params = std.extVar("__ksonnet/params").components["nfs-external"];
// TODO(https://github.com/ksonnet/ksonnet/issues/222): We have to add namespace as an explicit parameter
// because ksonnet doesn't support inheriting it from the environment yet.

local k = import "k.libsonnet";

local name = params.name;
local namespace = params.namespace;
local nfsServer = params.nfsServer;

local storageClassName = "gcfs-storage";

local pv = {
  apiVersion: "v1",
  kind: "PersistentVolume",
  metadata: {
    name: "gcfs",
    namespace: namespace,
  },
  spec: {
    accessModes: [
      "ReadWriteMany",
    ],
    capacity: {
      storage: "5Gi",
    },
    nfs: {
      path: "/kubeflow",
      server: nfsServer,
    },
    persistentVolumeReclaimPolicy: "Retain",
    storageClassName: storageClassName,
  },
};

local pvc = {
  apiVersion: "v1",
  kind: "PersistentVolumeClaim",
  metadata: {
    annotations: {
      "volume.beta.kubernetes.io/storage-class": storageClassName,
    },
    name: "nfs-external",
    namespace: namespace,
  },
  spec: {
    accessModes: [
      "ReadWriteMany",
    ],
    resources: {
      requests: {
        storage: "500Mi",
      },
    },
  },
};

std.prune(k.core.v1.list.new([
  pv,
  pvc,
]))
