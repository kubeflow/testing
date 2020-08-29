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
#
# For a pull request do
# {REPO_ORG}/{REPO_NAME}@{SHA}:{PULL_NUMBER}
#
# You can use HEAD as the sha to get the latest for a pull request.
#
# To checkout a specific branch (e.g. "v0.3-branch"), set the
# {BRANCH_NAME} environment variable.
set -xe

SRC_DIR=$1

mkdir -p /src/${REPO_OWNER}

# TODO(jlewi): We should eventually move the code for running the workflow from
# kubeflow/kubeflow into kubeflow/testing
# We need depth=2 so that we can compare commit with previous commit in postsubmit runs.
# We also need --no-single-branch because otherwise Git assumes there is only one branch,
# which causes periodic tests against non-master branches to fail.
git clone --depth=2 --no-single-branch https://github.com/${REPO_OWNER}/${REPO_NAME}.git ${SRC_DIR}/${REPO_OWNER}/${REPO_NAME}

echo Job Name = ${JOB_NAME}

# See https://github.com/kubernetes/test-infra/tree/master/prow#job-evironment-variables
REPO_DIR=${SRC_DIR}/${REPO_OWNER}/${REPO_NAME}
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

# Check out any extra repos.
IFS=';' read -ra REPOS <<< "${EXTRA_REPOS}"
echo REPOS=${REPOS}
for r in "${REPOS[@]}"; do
  echo "Processing ${r}" 
  ORG_NAME="$(cut -d'@' -f1 <<< "$r")"
  EXTRA_ORG="$(cut -d'/' -f1 <<< "$ORG_NAME")"
  EXTRA_NAME="$(cut -d'/' -f2<<< "$ORG_NAME")"
  SHA_AND_PR="$(cut -d'@' -f2 <<< "$r")"  
  SHA="$(cut -d':' -f1 <<< "$SHA_AND_PR")"  
  EXTRA_PR="$(cut -d':' -s -f2 <<< "$SHA_AND_PR")"
  URL=https://github.com/${EXTRA_ORG}/${EXTRA_NAME}.git
  TARGET=${SRC_DIR}/${EXTRA_ORG}/${EXTRA_NAME}
  if [ ! -d ${TARGET} ]; then
  	git clone  ${URL} ${TARGET}
  	cd ${TARGET}

  	if [ ! -z ${EXTRA_PR} ]; then
  		git fetch origin  pull/${EXTRA_PR}/head:pr
  		git checkout pr

	  	if [ "$SHA" -ne "HEAD" ]; then
	  		git checkout ${SHA}
		fi  		
  	else  	
  		git checkout ${SHA}
	fi  
	echo ${TARGET} is at `git describe --tags --always --dirty`
  else
  	echo Error ${TARGET} already exists not cloning ${URL}
  fi
done	

# Check out the kubeflow/testing repo (unless that's the repo being tested)
# since it contains common utilities.
# TODO(jlewi): We should get rid of this and just treat kubeflow/testing as
# an EXTRA_REPOS.
#if [ ! -d ${SRC_DIR}/kubeflow/testing ]; then
#	git clone --depth=1 https://github.com/kubeflow/testing.git ${SRC_DIR}/kubeflow/testing
#fi

###### Temporary work-around for testing

if [ ! -d ${SRC_DIR}/kubeflow/testing ]; then
	git clone --depth=1 --no-single-branch https://github.com/PatrickXYS/testing.git ${SRC_DIR}/kubeflow/testing
	cd ${SRC_DIR}/kubeflow/testing
  git fetch origin yao_aws_account
  git checkout -b yao_aws_account origin/yao_aws_account
fi

##########