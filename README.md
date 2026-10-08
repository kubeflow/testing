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
    base-reference: main
    # Optional: one regular expression per line; blank lines and # comments are ignored.
    exclude: |
      ^third_party/
      # Vendored go-sql-driver/mysql (MPL-2.0); keeps its upstream header.
      ^internal/starrocks/mysqldriver/
```

### contributor-report

Posts a comment on a pull request summarizing its author: Kubeflow org membership (from
[kubeflow/internal-acls](https://github.com/kubeflow/internal-acls)), GitHub account age, and the
issues and merged pull requests they have in the calling repository. If a report is already on the
pull request, it is edited in place rather than posted again.

The action runs its script from `kubeflow/testing`, so it does not need a checkout and never runs
pull-request code. Use the `pull_request_target` event so the report also works for pull requests
from forks. The report is about the author, which does not change between pushes, so run it only
when the pull request is opened:

```yaml
name: Contributor Report

on:
  pull_request_target:
    types: [opened]

permissions:
  contents: read
  pull-requests: write

jobs:
  contributor-report:
    if: github.event.pull_request.user.login != 'dependabot[bot]'
    runs-on: ubuntu-latest
    steps:
      - uses: kubeflow/testing/.github/actions/contributor-report@<commit-sha>
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          # Optional: print the report to the job log instead of commenting.
          # dry-run: "true"
```

To preview a report locally, run the script against a saved pull-request event payload:

```bash
pip install -r hack/contributor-report/requirements.txt
GITHUB_TOKEN="$(gh auth token)" GITHUB_REPOSITORY=kubeflow/pipelines \
  GITHUB_EVENT_PATH=event.json CONTRIBUTOR_REPORT_DRY_RUN=true \
  python hack/contributor-report/contributor_report.py
```

## Contributing

We welcome contributions to enhance support for common Kubeflow infrastructure! Please see our
[CONTRIBUTING guide](CONTRIBUTING.md) for details.
