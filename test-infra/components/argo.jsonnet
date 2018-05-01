local params = std.extVar("__ksonnet/params").components.argo;

local k = import "k.libsonnet";
local argo = import "argo.libsonnet";
local namespace = params.namespace;

local ingress = if params.exposeUi then
  [argo.parts(namespace).uiIngress]
else [];

std.prune(k.core.v1.list.new([
  argo.parts(namespace).crd,
  argo.parts(namespace).config,
  argo.parts(namespace).deploy,
  argo.parts(namespace).deployUi,
  argo.parts(namespace).uiService,
  argo.parts(namespace).serviceAccount,
  argo.parts(namespace).roleBinding,
  argo.parts(namespace).defaultRoleBinding,
] + ingress))
