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

_Work In Progress_

## Contributing

We welcome contributions to enhance support for common Kubeflow infrastructure! Please see our
[CONTRIBUTING guide](CONTRIBUTING.md) for details.
