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

### verify-boilerplate

Runs the license header check above against the calling repository. Check out the repository
with `fetch-depth: 0` first so the base branch can be resolved:

```yaml
- uses: actions/checkout@v5
  with:
    fetch-depth: 0
- uses: kubeflow/testing/.github/actions/verify-boilerplate@<commit-sha>
  with:
    base-ref: main
    # Optional: one regular expression per line; blank lines and # comments are ignored.
    exclude: |
      ^third_party/
      # Vendored go-sql-driver/mysql (MPL-2.0); keeps its upstream header.
      ^internal/starrocks/mysqldriver/
```

### pr-gate

Gates pull requests from external contributors on a maintainer-triaged issue:

1. Looks up the PR author in [`kubeflow/internal-acls` `org.yaml`](https://github.com/kubeflow/internal-acls/blob/master/github-orgs/kubeflow/org.yaml); Kubeflow org admins and members pass without further checks.
2. Exempts configured bot accounts (`dependabot[bot]` and `copybara-service[bot]` by default).
3. Requires external contributors to reference a same-repository closing issue (`Fixes #N` on its own line in the PR description, including for PRs targeting release branches) that carries the maintainer admission label (`ready` by default).
4. When admitted, adds `ok-to-test`, removes `needs-ok-to-test`, and approves pending `action_required` fork workflow runs. Otherwise comments with admission guidance and closes the PR.

Call it as a reusable workflow from `.github/workflows/pr-gate.yaml` in a consuming repository:

```yaml
name: PR Gate

on:
  pull_request_target:
    types: [opened, labeled, synchronize, reopened]

permissions:
  actions: write
  contents: read
  issues: read
  pull-requests: write

jobs:
  pr-gate:
    uses: kubeflow/testing/.github/workflows/pr-gate.yaml@<commit-sha>
```

Or invoke the composite action directly inside a job step:

```yaml
- uses: kubeflow/testing/.github/actions/pr-gate@<commit-sha>
  with:
    admission-label: ready
```

## Contributing

We welcome contributions to enhance support for common Kubeflow infrastructure! Please see our
[CONTRIBUTING guide](CONTRIBUTING.md) for details.
