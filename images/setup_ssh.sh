#!/bin/bash
#
# This script is used to setup a .ssh directory that mounts an SSH key.
#
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
  echo "Usage: setup_ssh.sh --ssh_dir=<path to ssh dir> --private_key=<path to private key> --public_key=<path to public_key>"
}

main() {

  cd "${DIR}"

  # List of required parameters
  names=(ssh_dir private_key public_key)

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

  mkdir -p ${ssh_dir}
  cp -f ${private_key} ${ssh_dir}
  cp -f ${public_key} ${ssh_dir}
  
  # Set the permissions
  chmod 700 ${ssh_dir}
  chmod 600 ${ssh_dir}/$(basename ${private_key})
  chmod 644 ${ssh_dir}/$(basename ${public_key})
}

parseArgs $*
main
