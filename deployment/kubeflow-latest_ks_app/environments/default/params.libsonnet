local params = std.extVar("__ksonnet/params");
local globals = import "globals.libsonnet";
local envParams = params {
  components+: {
    jupyterhub+: {
      disks: "github-issues-data",
      jupyterNotebookPVCMount: "/home/jovyan",
    },
  },
};

{
  components: {
    [x]: envParams.components[x] + globals
    for x in std.objectFields(envParams.components)
  },
}
