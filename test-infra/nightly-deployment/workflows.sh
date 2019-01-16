#!/bin/bash
#
# This script is meant to be the entrypoint for a prow job.
# It checkos out a repo and then looks for prow_config.yaml in that
# repo and uses that to run one or more workflows.
set -ex

# Check out repos we need.
/usr/local/bin/checkout.sh /src kubeflow kubeflow
/usr/local/bin/checkout.sh /src kubeflow testing

ls -R /src

# TODO(gabrielwen): Trigger create_kf_instance.py here.
