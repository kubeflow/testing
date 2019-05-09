// Oneoff job to cleanup the ci system.
//
local params = std.extVar("__ksonnet/params").components["cleanup-ci-cron"];
local env = std.extVar("__ksonnet/environments");

local k = import "k.libsonnet";
local cleanup = import "cleanup-ci.libsonnet";

local project = "kubeflow-ci";
local job(project, gcBackendServices) = {
    "apiVersion": "batch/v1beta1", 
    "kind": "CronJob", 
    "metadata": {           
      name: params.name + "-" + project,
      namespace: env.namespace,
      labels: {
        app: "cleanup-ci-" + project,
      },
    }, 
    spec: {
      // Every two hours
      schedule: "0 */2 * * *" , 
      concurrencyPolicy: "Forbid",
      jobTemplate: {
        metadata: {
          labels: {
            app: "cleanup-ci-" + project,
          },
        },
        spec: cleanup.jobSpec(project, gcBackendServices),
      },
    }, 
};

std.prune(k.core.v1.list.new([
  // Setup 2 cron jobs for the two projects.
  job("kubeflow-ci", false),
  job("kubeflow-ci-deployment", true),
]))
