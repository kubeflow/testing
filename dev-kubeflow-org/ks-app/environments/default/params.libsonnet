local params = std.extVar("__ksonnet/params");
local globals = import "globals.libsonnet";
local envParams = params {
  components+: {
    "kubeflow-core"+: {
      disks: "github-issues-data",
      jupyterNotebookPVCMount: "/home/jovyan",
      jupyterNotebookRegistry: "gcr.io",
      jupyterNotebookRepoName: "kubeflow-images-public",
      tfAmbassadorImage: "quay.io/datawire/ambassador:0.30.1",
      tfStatsdImage: "quay.io/datawire/statsd:0.30.1",
    },
  },
};

{
  components: {
    [x]: envParams.components[x] + globals
    for x in std.objectFields(envParams.components)
  },
}
