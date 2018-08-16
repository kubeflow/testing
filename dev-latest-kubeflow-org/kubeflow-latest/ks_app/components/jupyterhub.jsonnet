local env = std.extVar("__ksonnet/environments");
local params = std.extVar("__ksonnet/params").components.jupyterhub;

// updatedParams uses the environment namespace if
// the namespace parameter is not explicitly set
local updatedParams = params {
  namespace: if params.namespace == "null" then env.namespace else params.namespace,
};

local jupyterhub = import "kubeflow/core/jupyterhub.libsonnet";
jupyterhub.parts(updatedParams)
