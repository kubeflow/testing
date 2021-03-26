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
# You can use "--links" to create symbolic links to the newly created directories.
# This allows you to check out forks of the Kubeflow repos but lay them out as if you
# checked out the original repos so that you can use scripts that depend on that layout.
#
#
# By default repositories are cloned with depth 2. You can specify the depth with 
# --depth
# To avoid doing a shallow clone set --depth=all
set -xe

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

#set the default value for depth
depth="2"

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
  echo "Usage: checkout_repos --repos=<{REPO_ORG}/{REPO_NAME}@{SHA}:{PULL_NUMBER},{REPO_ORG}/{REPO_NAME}@HEAD:{PULL_NUMBER}> --src_dir=<Where to check them out> --links=<src1>=<dest1>,<src2>=<dest2> --depth=<number | all>"
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
  IFS=',' read -ra SPLIT_REPOS <<< "${repos}"
  echo SPLIT_REPOS=${SPLIT_REPOS}
  for r in "${SPLIT_REPOS[@]}"; do
    echo "Processing ${r}" 
    ORG_NAME="$(cut -d'@' -f1 <<< "$r")"
    EXTRA_ORG="$(cut -d'/' -f1 <<< "$ORG_NAME")"
    EXTRA_NAME="$(cut -d'/' -f2<<< "$ORG_NAME")"
    SHA_AND_PR="$(cut -d'@' -f2 <<< "$r")"  
    SHA="$(cut -d':' -f1 <<< "$SHA_AND_PR")"  
    EXTRA_PR="$(cut -d':' -s -f2 <<< "$SHA_AND_PR")"
    URL=https://github.com/${EXTRA_ORG}/${EXTRA_NAME}.git
    TARGET=${src_dir}/${EXTRA_ORG}/${EXTRA_NAME}
    PULL_BASE_REF="${PULL_BASE_REF:-master}"

    mkdir -p ${src_dir}/${EXTRA_ORG}

    if [ ! -d ${TARGET} ]; then
      if [ "${depth}" == "all" ]; then
        git clone  ${URL} ${TARGET}
      else
        git clone --depth=${depth} ${URL} ${TARGET}
      fi
    else
      # init containers might get restarted so its possible we already checked out the repo
      echo ${TARGET} already exists
    fi

    cd ${TARGET}

    if [ ! -z ${EXTRA_PR} ]; then
      git fetch origin  pull/${EXTRA_PR}/head:pr
      git checkout pr

      if [ "$SHA" -ne "HEAD" ]; then
        git fetch origin ${PULL_BASE_REF}
        git checkout ${SHA}
      fi      
    else
      git fetch origin ${PULL_BASE_REF}
      git checkout ${SHA}
    fi
    echo ${TARGET} is at `git describe --tags --always --dirty`
  done  

  IFS=',' read -ra LINKS <<< "${links}"
  echo LINKS=${LINKS}
  for r in "${LINKS[@]}"; do
    link_src="$(cut -d'=' -f1 <<< "$r")"
    link_dest="$(cut -d'=' -f2<<< "$r")"
    # Ensure parent directory exists
    mkdir -p $(dirname ${src_dir}/${link_dest})
    ln -sf ${src_dir}/${link_src} ${src_dir}/${link_dest}
  done
}

parseArgs $*
main
