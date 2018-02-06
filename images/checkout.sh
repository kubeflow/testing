#!/bin/bash
#
# This script is used to bootstrap our prow jobs.
# The point of this script is to check out repositories
# at the commit corresponding to the Prow job. 
#
# In addition to understanding the prow environment variables.
# the environment variable EXTRA_REPOS can be used to specify
# extra GitHub repositories to checkout.
# EXTRA_REPOS should be a ; delimited list of the form
# {REPO_ORG}/{REPO_NAME}@{SHA}

set -xe

SRC_DIR=$1

mkdir -p /src/${REPO_OWNER}

# TODO(jlewi): We should eventually move the code for running the workflow from
# kubeflow/kubeflow into kubeflow/testing
git clone https://github.com/${REPO_OWNER}/${REPO_NAME}.git ${SRC_DIR}/${REPO_OWNER}/${REPO_NAME}

echo Job Name = ${JOB_NAME}

# See https://github.com/kubernetes/test-infra/tree/master/prow#job-evironment-variables
cd ${SRC_DIR}/${REPO_OWNER}/${REPO_NAME}
if [ ! -z ${PULL_NUMBER} ]; then
 git fetch origin  pull/${PULL_NUMBER}/head:pr
 git checkout ${PULL_PULL_SHA}
else
 if [ ! -z ${PULL_BASE_SHA} ]; then
 	# Its a post submit; checkout the commit to test.
  	git checkout ${PULL_BASE_SHA}
 fi
fi

# Update submodules.
git submodule init
git submodule update

# Print out the commit so we can tell from logs what we checked out.
echo Repo is at `git describe --tags --always --dirty`
git submodule
git status

# Check out any extra repos.
IFS=';' read -ra EXTRA_REPOS <<< "${EXTRA_REPOS}"
for r in "${REPOS[@]}"; do
  echo "Repo ${r}" 
  ORG_NAME="$(cut -d'@' -f1 <<< "$r")"
  EXTRA_ORG="$(cut -d'/' -f1 <<< "$ORG_NAME")"
  EXTRA_NAME="$(cut -d'/' -f2<<< "$ORG_NAME")"
  SHA="$(cut -d'@' -f2 <<< "$r")"  
  URL=https://github.com/${EXTRA_ORG}/${EXTRA_NAME}.git
  TARGET=${SRC_DIR}/${EXTRA_ORG}/${EXTRA_NAME}
  if [ ! -d ${TARGET} ]; then
  	git clone  ${URL} ${TARGET}
  	cd ${TARGET}
  	git checkout ${SHA}
  else
  	echo Error ${TARGET} already exists not cloning ${URL}
  fi
done	

# Check out the kubeflow/testing repo (unless that's the repo being tested)
# since it contains common utilities.
# TODO(jlewi): We might want to eventually pin to a particular version that is known to be good.
if [ ! -d /src/kubeflow/testing ]; then
	git clone https://github.com/kubeflow/testing.git ${SRC_DIR}/kubeflow/testing
fi	
