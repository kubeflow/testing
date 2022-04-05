# Test infra for KFP (Kubeflow Pipelines)

## Upgrade KFP

1. (Optionally) Run:

    ```bash
    make hydrate-kfp-manifests
    ```
    
    To check the generated raw k8s resources in acm-repos folder based on local changes (without pulling manifests from kfp repo). 

1. Edit `PIPELINES_VERSION=<new-version>` in Makefile.

1. Run:

    ```bash
    make kfp-update
    ```

    It generates raw k8s resources in acm-repos folder which is source of truth for the cluster via gitops.

1. Commit the changes and send a PR.
