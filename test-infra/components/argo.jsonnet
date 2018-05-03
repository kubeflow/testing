local params = std.extVar("__ksonnet/params").components.argo;

local k = import "k.libsonnet";
local argo = import "argo.libsonnet";
local namespace = params.namespace;

local version = "v2.1.0";

local ingress = if params.exposeUi then
  [argo.parts(namespace, version).uiIngress]
else [];

std.prune(k.core.v1.list.new([
  argo.parts(namespace, version).crd,
  argo.parts(namespace, version).argoServiceAccount,
  argo.parts(namespace, version).argoClusterRole,
  argo.parts(namespace, version).argoClusterRoleBinding,
  argo.parts(namespace, version).argoDeployment,
  argo.parts(namespace, version).argoConfigMap,
  argo.parts(namespace, version).argoUiServiceAccount,
  argo.parts(namespace, version).argoUiClusterRole,
  argo.parts(namespace, version).argoUiClusterRoleBinding,
  argo.parts(namespace, version).argoUiService,
  argo.parts(namespace, version).argoUiDeployment,
] + ingress))
