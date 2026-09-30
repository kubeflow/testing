#!/usr/bin/env bash

# Copyright The Kubeflow Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail

if (( $# < 1 )); then
  echo "Usage: $0 <primary-image> [fallback-image ...]" >&2
  exit 1
fi

primary_image=$1
shift
fallback_images=("$@")
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=retry.sh
source "${script_dir}/retry.sh"

pull_image() {
  local image=$1
  echo "Pulling ${image} with retries"
  retry 3 20 docker pull "${image}"
}

if pull_image "${primary_image}"; then
  exit 0
fi

for fallback_image in "${fallback_images[@]}"; do
  echo "Falling back to ${fallback_image} for ${primary_image}"
  if pull_image "${fallback_image}"; then
    if [[ "${fallback_image}" != "${primary_image}" ]]; then
      docker tag "${fallback_image}" "${primary_image}"
    fi
    exit 0
  fi
done

echo "Failed to pull ${primary_image} and all configured fallbacks" >&2
exit 1
