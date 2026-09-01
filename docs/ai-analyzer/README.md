# AI issue quality analyzer

The AI analyzer reviews newly opened GitHub issues for scope, context, guidance,
and complexity. It runs in the **calling repository's GitHub Actions**, using
that repository's issue event and `GITHUB_TOKEN`.

The workflow source is
[`ai-analyzer.md`](../../.github/workflows/ai-analyzer.md). Callers reference its
compiled [`ai-analyzer.lock.yml`](../../.github/workflows/ai-analyzer.lock.yml).

## Prerequisites

- Enable GitHub Actions and Copilot access for Actions in the consuming
  repository or organization, including the `copilot-requests: write` permission.
- Allow this reusable workflow and its referenced actions in your Actions policy.
- Choose a published commit in `kubeflow/testing` containing both the compiled
  workflow and [Python validator](../../.github/scripts/issue_parser.py).
  The shared repository must be publicly readable for this setup to use the
  caller's `GITHUB_TOKEN` without additional credentials.

## Call the workflow

Create `.github/workflows/ai-analyzer.yml` in your repository:

```yaml
name: AI issue quality analyzer

on:
  issues:
    types: [opened]

permissions:
  actions: read
  contents: read
  issues: write
  copilot-requests: write

jobs:
  analyze:
    uses: kubeflow/testing/.github/workflows/ai-analyzer.lock.yml@<commit-sha>
```

Replace `<commit-sha>` with the full commit SHA you selected, then merge this
file into your repository's default branch. You do not need to copy the Python
script, install the workflow compiler, or use `secrets: inherit`.

Each caller run must reference exactly one version of `ai-analyzer.lock.yml`.
The workflow resolves that version's commit and checks out the validator from
the shared repository at that same commit.

## Verify a run

Open a new issue in your repository with a title such as:

```text
bug(sdk): Pipeline compilation fails for an empty parameter
```

Titles use `<type>(<area>): <description>`. Supported types are `bug`, `chore`,
and `feat`; the area must contain lowercase letters. Include enough detail in
the issue body for a useful review.

Find the run in **your repository's Actions tab**. A valid title proceeds to the
AI review, subject to rate and usage limits. An invalid title receives a format
validation comment and skips the AI review. Editing an existing issue does not
trigger this caller configuration.

Opening an issue in `kubeflow/testing` does not itself trigger the shared
workflow: its trigger is `workflow_call`.

## Inputs and environment variables

The caller passes configuration through `with` and credentials through
`secrets`. The shared workflow maps these values to the Python step's environment:

| Caller field | Python environment variable | Default when omitted |
| --- | --- | --- |
| `with.issue-number` | `ISSUE_NUMBER` | Triggering issue number |
| `with.issue-title` | `ISSUE_TITLE` | Triggering issue title |
| `with.issue-samples` | `ISSUE_SAMPLES` | `{}` |
| `with.title-pattern` | `TITLE_PATTERN` | Conventional title regex shown above |
| `with.repo` | `REPO` | Caller repository |
| `secrets.gh-token` | `GH_TOKEN` | Caller `GITHUB_TOKEN` |

See [sample-call.yaml](../../sample-call.yaml) for a caller providing all six.
The title pattern must capture the issue type and area as groups 1 and 2.
An empty title or repository, or an issue number of zero, uses the event default.
The supplied token is used for Python validation comments; the other workflow
jobs retain their existing authentication. Keep the repository and issue number
aligned with the triggering event, which still determines the AI review target.

### Reference samples

Pass a JSON mapping of issue types to sample text using the caller job's
`with.issue-samples` input. The shared workflow forwards it to the Python
validator as the `ISSUE_SAMPLES` environment variable. For example, add this
alongside the caller job's `uses`:

```yaml
    with:
      issue-samples: |
        {"bug": "Your reference bug report sample", "feat": "Your feature request sample"}
```

The input defaults to `{}`. Issue types without a sample use the generic review
fallback; malformed JSON or invalid sample values fail validation. The AI prompt
still uses a Kubeflow Pipelines maintainer role.

## Maintaining the shared workflow

Edit `ai-analyzer.md` for workflow or prompt changes, and edit
`.github/scripts/issue_parser.py` for validation changes. From this repository's
root, compile workflow changes with GitHub Agentic Workflows **v0.88.7**:

```bash
gh aw compile ai-analyzer
gh aw compile ai-analyzer --no-emit --validate
python -m unittest discover -s .github/scripts -p 'test_*.py' -v
```

Commit the Markdown source and generated `.lock.yml` together. Publish script
changes alongside the workflow version consumers will reference. Consumers
adopt updates by changing the commit SHA in their caller workflow.
