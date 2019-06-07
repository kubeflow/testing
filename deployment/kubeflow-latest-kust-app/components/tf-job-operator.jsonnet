local env = std.extVar("__ksonnet/environments");
local params = std.extVar("__ksonnet/params").components["tf-job-operator"];

local k = import "k.libsonnet";
local tfjob = import "kubeflow/core/tf-job-operator.libsonnet";

// updatedParams uses the environment namespace if
// the namespace parameter is not explicitly set
local updatedParams = params {
  namespace: if params.namespace == "null" then env.namespace else params.namespace,
};

std.prune(k.core.v1.list.new(tfjob.all(updatedParams)))
