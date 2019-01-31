#!/bin/bash
# Simple way to take a snapshot of a github repository at a given commit.
set -xe

SRC_DIR=$1
REPO_OWNER=$2
REPO_NAME=$3
COMMIT_SHA=$4

ORIGIN_DIR=$PWD

mkdir -p ${SRC_DIR}/${CHECKOUT_REPO_OWNER}
REPO_DIR=${SRC_DIR}/${CHECKOUT_REPO_OWNER}/${CHECKOUT_REPO_NAME}

echo "Checking out git repo: ${CHECKOUT_REPO_OWNER}/${CHECKOUT_REPO_NAME}.git"
git clone https://github.com/${CHECKOUT_REPO_OWNER}/${CHECKOUT_REPO_NAME}.git ${REPO_DIR}

cd ${REPO_DIR}

echo "Taking snapshot at ${COMMIT_SHA}"
git reset --hard ${COMMIT_SHA}

cd ${ORIGIN_DIR}
