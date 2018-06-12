local env = std.extVar("__ksonnet/environments");
local params = std.extVar("__ksonnet/params").components["iap-ingress"];

local k = import "k.libsonnet";
local iap = import "kubeflow/core/iap.libsonnet";
local util = import "kubeflow/core/util.libsonnet";

// updatedParams uses the environment namespace if
// the namespace parameter is not explicitly set
local updatedParams = params {
  namespace: if params.namespace == "null" then env.namespace else params.namespace,
};

local namespace = updatedParams.namespace;
local disableJwtChecking = util.toBool(params.disableJwtChecking);

iap.parts(namespace).ingressParts(params.secretName, params.ipName, params.hostname, params.issuer, params.envoyImage, disableJwtChecking, params.oauthSecretName)
