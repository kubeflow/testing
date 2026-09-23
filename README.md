# Kubeflow Testing

This repository hosts shared CI building blocks for the Kubeflow community: reusable GitHub Actions
and scripts that any Kubeflow Subproject can consume from its own `.github/workflows` or `Makefile`.
The goal is to reduce duplication across Kubeflow repositories and to give the maintainers one place
to align on CI best practices.

## Common Scripts

The following scripts are available.

### Checking license headers

Every source file needs the Apache 2.0 header from `hack/boilerplate/`. New files must use the
year-less header (`Copyright The Kubeflow Authors.`). The verifier rejects a hardcoded year on
files added relative to the base branch.

Run this script as follows:

```bash
python hack/boilerplate/boilerplate.py --base-ref master
```

## Common GitHub Actions

The following GitHub actions are available.

### Create a Kind cluster

The `create-cluster` action provisions a Kind cluster for Kubernetes integration tests. It accepts
the Kubernetes version, node image, and cluster type explicitly, exports an absolute `KUBECONFIG`
path for subsequent steps, and also exposes that path as an action output.

```yaml
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1

      - name: Create Kind cluster
        id: kind
        uses: kubeflow/testing/.github/actions/create-cluster@378b6b94b24a948a5f440986e6b60b691636ff64 # create-cluster action
        with:
          k8s_version: v1.35.0
          node_image: kindest/node:v1.35.0
          cluster_type: cpu
          cluster_name: kubeflow

      - name: Inspect cluster
        run: kubectl get nodes
```

`cluster_name`, `kind_version`, and `wait` are optional. `cluster_type` defaults to `cpu`; set it to `gpu`
on a GPU runner with `nvkind` and the NVIDIA Container Toolkit installed. GPU mode configures the
NVIDIA runtime and creates the cluster with `nvkind`. GPU operator and other Kubeflow tool installation
remain caller responsibilities. The Kubernetes version should match the version in the selected Kind
node image. Keep cluster creation separate from installing Kubeflow subprojects or other test
dependencies so callers can compose the setup they need.

## Contributing

We welcome contributions to enhance support for common Kubeflow infrastructure! Please see our
[CONTRIBUTING guide](CONTRIBUTING.md) for details.
