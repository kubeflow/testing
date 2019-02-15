#!/bin/bash
# Simple way to take a snapshot of a github repository at a given commit.
set -xe

# Include library that helps on argument parsing.
. /usr/local/lib/lib-args.sh

required_args=(src_dir repo_owner repo_name branch commit_sha)
parseArgs $*
validateRequiredArgs ${required_args}

ORIGIN_DIR=$PWD

mkdir -p ${src_dir}/${repo_owner}
REPO_DIR=${src_dir}/${repo_owner}/${repo_name}

echo "Checking out git repo: ${repo_owner}/${repo_name}.git at branch ${branch}"
git clone --single-branch --branch ${branch} \
  https://github.com/${repo_owner}/${repo_name}.git ${REPO_DIR}

cd ${REPO_DIR}

echo "Taking snapshot at ${commit_sha}"
git reset --hard ${commit_sha}

cd ${ORIGIN_DIR}
