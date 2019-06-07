local env = std.extVar("__ksonnet/environments");
local params = std.extVar("__ksonnet/params").components["gpu-driver"];

local gpuDriver = import "kubeflow/gcp/gpu-driver.libsonnet";
local instance = gpuDriver.new(env, params);
instance.list(instance.all)
