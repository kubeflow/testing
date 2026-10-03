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

Vendored third-party code that must keep its upstream license header can be skipped with
`--exclude`, which takes a Python regular expression matched (with `re.search`) against each
file's repository-relative path. Repeat the flag for multiple patterns:

```bash
python hack/boilerplate/boilerplate.py --base-ref main \
  --exclude '^third_party/' \
  --exclude '^internal/starrocks/mysqldriver/'
```

## Common GitHub Actions

The following GitHub actions are available.

### Create a Kind cluster

The `create-cluster` action provisions a Kind cluster for Kubernetes integration tests. It follows
the setup used by Kubeflow Pipelines CI: it frees runner disk space when needed, configures the
Docker Hub mirror, caches the Kind node image, retries image pulls and cluster creation, and removes
the kindnet CPU limit. It exports an absolute `KUBECONFIG` path for subsequent steps and also exposes
that path as an action output.

```yaml
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1

      - name: Create Kind cluster
        id: kind
        uses: kubeflow/testing/.github/actions/create-cluster@f6dc12513635cb4c24d56cb4c69bde7223381bcd # create-cluster action
        with:
          k8s_version: v1.36.1
          node_image: kindest/node:v1.36.1
          cluster_name: kubeflow

      - name: Inspect cluster
        run: kubectl get nodes
```

`cluster_name` and `kind_version` are optional. The Kubernetes version should match the version in
the selected Kind node image. The action is tested with Kubernetes v1.33.12 and v1.36.1. GPU cluster
support is outside this action's current scope. Keep cluster creation separate from installing
Kubeflow subprojects or other test dependencies so callers can compose the setup they need.
### verify-boilerplate

Runs the license header check above against the calling repository. Check out the repository
with `fetch-depth: 0` first so the base branch can be resolved:

```yaml
- uses: actions/checkout@v5
  with:
    fetch-depth: 0
- uses: kubeflow/testing/.github/actions/verify-boilerplate@<commit-sha>
  with:
    base-reference: main
    # Optional: one regular expression per line; blank lines and # comments are ignored.
    exclude: |
      ^third_party/
      # Vendored go-sql-driver/mysql (MPL-2.0); keeps its upstream header.
      ^internal/starrocks/mysqldriver/
```

## Contributing

We welcome contributions to enhance support for common Kubeflow infrastructure! Please see our
[CONTRIBUTING guide](CONTRIBUTING.md) for details.
