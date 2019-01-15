#!/bin/bash
# We need to clone both kubeflow/kubeflow and kubeflow/testing for dpeloyhment.
set -xe

SRC_DIR=$1
CHECKOUT_REPO_OWNER=$2
CHECKOUT_REPO_NAME=$3

mkdir -p ${SRC_DIR}

echo "Checking out git repo: ${CHECKOUT_REPO_OWNER}/${CHECKOUT_REPO_NAME}.git"
git clone https://github.com/${CHECKOUT_REPO_OWNER}/${CHECKOUT_REPO_NAME}.git \
  ${SRC_DIR}/${CHECKOUT_REPO_NAME}

REPO_DIR=${SRC_DIR}/${CHECKOUT_REPO_OWNER}/${CHECKOUT_REPO_NAME}
cd ${REPO_DIR}
if [ ! -z ${PULL_NUMBER} ]; then
 git fetch origin  pull/${PULL_NUMBER}/head:pr
 if [ ! -z ${PULL_PULL_SHA} ]; then
 	git checkout ${PULL_PULL_SHA}
 else
 	git checkout pr
 fi

elif [ ! -z ${BRANCH_NAME} ]; then
  # Periodic jobs don't have pull numbers or commit SHAs, so we pass in the
  # branch name from the config yaml file.
  git fetch origin
  git checkout ${BRANCH_NAME}
 
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
echo ${REPO_DIR} is at `git describe --tags --always --dirty`
git submodule
git status
