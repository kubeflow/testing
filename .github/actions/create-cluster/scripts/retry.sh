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

retry() {
  local max_attempts=$1
  local interval=$2
  shift 2

  local attempt=1
  until "$@"; do
    if (( attempt >= max_attempts )); then
      return 1
    fi
    echo "Retrying in ${interval}s (attempt $((attempt + 1))/${max_attempts})..." >&2
    sleep "${interval}"
    attempt=$((attempt + 1))
  done
}
