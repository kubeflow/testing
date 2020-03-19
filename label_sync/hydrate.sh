#!/bin/bash
# a simple script to generate hydrated manifests
set -ex
# Remove previous instances
rm -f acm_repo/namespaces/*label-sync*
kustomize build -o acm_repo/namespaces