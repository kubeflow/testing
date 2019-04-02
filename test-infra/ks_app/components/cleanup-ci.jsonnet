// Oneoff job to cleanup the ci system.
//
local params = std.extVar("__ksonnet/params").components["cleanup-ci"];
local env = std.extVar("__ksonnet/environments");

local k = import "k.libsonnet";
local cleanup = import "cleanup-ci.libsonnet";

local job(project) = {
    "apiVersion": "batch/v1", 
    "kind": "Job", 
    "metadata": {           
      name: params.name + "-" + project,
      namespace: env.namespace,
      labels: {
        app: "cleanup-ci" + "-" + project,
      },
    }, 
    "spec": cleanup.jobSpec(project),
};

std.prune(k.core.v1.list.new([  
  job("kubeflow-ci"),
  job("kubeflow-ci-deployment"),
]))
