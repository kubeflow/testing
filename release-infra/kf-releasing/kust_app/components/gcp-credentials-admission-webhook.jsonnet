local env = std.extVar("__ksonnet/environments");
local params = std.extVar("__ksonnet/params").components["gcp-credentials-admission-webhook"];

local webhook = import "kubeflow/gcp/webhook.libsonnet";
local instance = webhook.new(env, params);
instance.list(instance.all)
