// Oneoff job to cleanup the ci system.
//
local params = std.extVar("__ksonnet/params").components["cleanup-ci"];
local env = std.extVar("__ksonnet/environments");

local k = import "k.libsonnet";
local cleanup = import "cleanup-ci.libsonnet";

local job = {
    "apiVersion": "batch/v1", 
    "kind": "Job", 
    "metadata": {           
      name: params.name,
      namespace: env.namespace,
      labels: {
        job: "cleanup-ci"
      },
    }, 
    "spec": cleanup.jobSpec,
};

std.prune(k.core.v1.list.new([  
  job,
]))
