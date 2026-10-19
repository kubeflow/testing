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

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=retry.sh
source "${script_dir}/retry.sh"

docker_daemon_config="${DOCKER_DAEMON_CONFIG:-/etc/docker/daemon.json}"
docker_hub_mirror="${DOCKER_HUB_MIRROR:-https://mirror.gcr.io}"
privilege_command=()
if [[ "${EUID}" -ne 0 ]]; then
  privilege_command=(sudo)
fi

configuration_status=$("${privilege_command[@]}" python3 \
  "${script_dir}/configure_docker_registry_mirror.py" \
  --config "${docker_daemon_config}" \
  --mirror "${docker_hub_mirror}")

if [[ "${configuration_status}" == "changed" ]]; then
  "${privilege_command[@]}" systemctl restart docker
elif [[ "${configuration_status}" != "unchanged" ]]; then
  echo "Unexpected Docker mirror status: ${configuration_status}" >&2
  exit 1
fi

docker_information=$(retry 10 2 docker info)
if ! grep -Fq "${docker_hub_mirror}" <<< "${docker_information}"; then
  echo "Docker did not report the configured mirror: ${docker_hub_mirror}" >&2
  exit 1
fi

echo "Docker Hub mirror configured: ${docker_hub_mirror}"
