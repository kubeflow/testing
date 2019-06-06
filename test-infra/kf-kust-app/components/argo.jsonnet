local params = std.extVar("__ksonnet/params").components.argo;
local env = std.extVar("__ksonnet/environments");

local k = import "k.libsonnet";
local argo = import "argo.libsonnet";

local version = "v2.2.1";

local ingress = if params.exposeUi then
  [argo.parts(env, params).uiIngress]
else [];

std.prune(k.core.v1.list.new([
  argo.parts(env, params).crd,
  argo.parts(env, params).argoServiceAccount,
  argo.parts(env, params).argoClusterRole,
  argo.parts(env, params).argoClusterRoleBinding,
  argo.parts(env, params).argoDeployment,
  argo.parts(env, params).argoConfigMap,
  argo.parts(env, params).argoUiServiceAccount,
  argo.parts(env, params).argoUiClusterRole,
  argo.parts(env, params).argoUiClusterRoleBinding,
  argo.parts(env, params).argoUiService,
  argo.parts(env, params).argoUiDeployment,
] + ingress))
