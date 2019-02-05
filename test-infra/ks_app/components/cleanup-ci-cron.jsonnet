// Oneoff job to cleanup the ci system.
//
local params = std.extVar("__ksonnet/params").components["cleanup-ci-cron"];
local env = std.extVar("__ksonnet/environments");

local k = import "k.libsonnet";
local cleanup = import "cleanup-ci.libsonnet";

local job = {
    "apiVersion": "batch/v1beta1", 
    "kind": "CronJob", 
    "metadata": {           
      name: params.name,
      namespace: env.namespace,
      labels: {
        app: "cleanup-ci"
      },
    }, 
    spec: {
      // Every two hours
      schedule: "0 */2 * * *" , 
      concurrencyPolicy: "Forbid",
      jobTemplate: {
        metadata: {
          labels: {
            app: "cleanup-ci",
          },
        },
        spec: cleanup.jobSpec,
      },
    }, 
};

std.prune(k.core.v1.list.new([  
  job,
]))
