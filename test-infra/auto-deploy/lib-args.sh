#!/bin/bash
# Utility functions used to parse passed arguments.
set -ex

parseArgs() {
  # Parse all command line options
  while [[ $# -gt 0 ]]; do
    # Parameters should be of the form
    # --{name}=${value}
    echo parsing "$1"
    if [[ $1 =~ ^--(.*)=(.*)$ ]]; then
      _name=${BASH_REMATCH[1]}
      _value=${BASH_REMATCH[2]}

      eval ${_name}="${_value}"
    elif [[ $1 =~ ^--(.*)$ ]]; then
    _name=${BASH_REMATCH[1]}
    _value=true
    eval ${_name}="${_value}"
    else
      echo "Argument $1 did not match the pattern --{name}={value} or --{name}"
      exit 1
    fi
    shift
  done
}

validateRequiredArgs() {
  local _names=$1
  for i in ${_names[@]}; do
    if [ -z ${!i} ]; then
      echo "--${i} not set."
      exit 1
    fi
  done
}

# args=(foo bar baz)
# parseArgs $*
# validateRequiredArgs ${args}
