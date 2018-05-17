#!/bin/bash
#
# This script is meant to be the entrypoint for a release workflow job.
# It checkos out repos needed and then trigger release workflows in prow_config_release.yaml.
# As of today 05/17/2018, image release will use master head.
set -ex

# Checkout the code.
/usr/local/bin/checkout.sh /src
eval

# Trigger a workflow
python -m kubeflow.testing.run_e2e_workflow \
  --project=kubeflow-releasing \
  --zone=us-central1-a \
  --cluster=kubeflow-releasing \
  --bucket=kubeflow-releasing-artifacts \
  --config_file=/src/kubeflow/kubeflow/releasing/prow_config_release.yaml \
  --repos_dir=/src \
  --release
