#!/bin/bash
#
# This script is used to checkout repositories.
# This is typically used to bootstrap various scripts
# by first checking out the code in an init container.
#
# For a pull request do
# {REPO_ORG}/{REPO_NAME}@{SHA}:{PULL_NUMBER}
#
# You can use HEAD as the sha to get the latest for a pull request.
#
#
# TODO(jlewi): We should provide some syntax for mapping the org and repo name
# to a different directory when checked out. The motivation would be to support
# easily pulling repos from a fork (e.g. jlewi/kubeflow) while still having the 
# local paths match what they would be for the main repo e.g. /src/kubeflow/kubeflow
#
# An easy way to do that might be to have another command line argument that specifies
# symbolic links to create e.g. --links=jlewi/kubeflow=kubeflow/kubeflow could mean run
# ln -sf /src/jlewi/kubeflow /src/kubeflow/kubeflow
set -xe

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

parseArgs() {
  # Parse all command line options
  while [[ $# -gt 0 ]]; do
    # Parameters should be of the form
    # --{name}=${value}
    echo parsing "$1"
    if [[ $1 =~ ^--(.*)=(.*)$ ]]; then
      name=${BASH_REMATCH[1]}
      value=${BASH_REMATCH[2]}

      eval ${name}="${value}"
    elif [[ $1 =~ ^--(.*)$ ]]; then
    name=${BASH_REMATCH[1]}
    value=true
    eval ${name}="${value}"
    else
      echo "Argument $1 did not match the pattern --{name}={value} or --{name}"
    fi
    shift
  done
}

usage() {
  echo "Usage: checkout_repos --repos=<{REPO_ORG}/{REPO_NAME}@{SHA}:{PULL_NUMBER};{REPO_ORG}/{REPO_NAME}@HEAD:{PULL_NUMBER}> --src_dir=<Where to check them out>"
}

main() {

  cd "${DIR}"

  # List of required parameters
  names=(repos src_dir)

  missingParam=false
  for i in ${names[@]}; do
    if [ -z ${!i} ]; then
      echo "--${i} not set"
      missingParam=true
    fi
  done

  if ${missingParam}; then
    usage
    exit 1
  fi

  # Check out any extra repos.
  IFS=';' read -ra REPOS <<< "${repos}"
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
    TARGET=${src_dir}/${EXTRA_ORG}/${EXTRA_NAME}

    mkdir -p ${src_dir}/${EXTRA_ORG}
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
  done  
}

parseArgs $*
main
