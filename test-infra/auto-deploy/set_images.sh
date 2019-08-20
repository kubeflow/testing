#!/bin/bash
# A simple shell scripy to set the images in the yaml files
set -ex

IMAGE=$1

substitute() {
	WHAT=$1
	TARGET=$2

	yq --yaml-output -r ${WHAT} ${TARGET} > /tmp/${TARGET}.new
	mv /tmp/${TARGET}.new ${TARGET}
}
#
substitute ".spec.template.spec.containers[0].image=\"${IMAGE}\"" deploy-master.yaml
substitute ".spec.jobTemplate.spec.template.spec.containers[0].image=\"${IMAGE}\"" deploy-cron-master.yaml
substitute ".spec.jobTemplate.spec.template.spec.containers[0].image=\"${IMAGE}\"" deploy-cron-v0-6.yaml