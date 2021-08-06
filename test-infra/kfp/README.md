# Test infra for KFP (Kubeflow Pipelines)

## Upgrade KFP

1. Edit `PIPELINES_VERSION=<new-version>` in Makefile.

1. Run:

    ```bash
    make kfp-update
    ```

1. Commit the changes and send a PR.
