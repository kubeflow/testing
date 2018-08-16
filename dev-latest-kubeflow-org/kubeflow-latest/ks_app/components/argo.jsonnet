local env = std.extVar("__ksonnet/environments");
local params = std.extVar("__ksonnet/params").components.argo;

local k = import "k.libsonnet";
local argo = import "kubeflow/argo/argo.libsonnet";

// updatedParams uses the environment namespace if
// the namespace parameter is not explicitly set
local updatedParams = params {
  namespace: if params.namespace == "null" then env.namespace else params.namespace,
};

local namespace = updatedParams.namespace;
local imageTag = params.imageTag;

std.prune(k.core.v1.list.new(argo.parts(namespace, imageTag).all))
