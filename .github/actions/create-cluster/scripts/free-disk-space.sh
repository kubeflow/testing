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

if [[ "${GITHUB_ACTIONS:-false}" != "true" ]]; then
  echo "This script is only intended for GitHub Actions runners" >&2
  exit 1
fi

minimum_free_gib="${MIN_FREE_SPACE_GIB:-60}"
if ! [[ "${minimum_free_gib}" =~ ^[0-9]+$ ]]; then
  echo "MIN_FREE_SPACE_GIB must be a non-negative integer" >&2
  exit 1
fi

available_kib=$(df -Pk / | awk 'NR == 2 {print $4}')
required_kib=$((minimum_free_gib * 1024 * 1024))
if [[ "${available_kib}" =~ ^[0-9]+$ ]] && (( available_kib >= required_kib )); then
  echo "Skipping disk cleanup: at least ${minimum_free_gib} GiB is available"
  exit 0
fi

echo "Freeing disk space before creating the Kind cluster"
df -h /

sudo rm -rf /usr/share/dotnet
sudo rm -rf /opt/ghc
sudo rm -rf /usr/local/share/boost
sudo rm -rf /usr/local/lib/android
sudo rm -rf /usr/local/.ghcup
sudo rm -rf /usr/share/swift
sudo rm -rf /opt/hostedtoolcache/CodeQL || true
sudo rm -rf /opt/hostedtoolcache/Java_* || true
sudo rm -rf /opt/hostedtoolcache/Ruby || true
sudo rm -rf /opt/hostedtoolcache/PyPy || true
sudo rm -rf /opt/hostedtoolcache/boost || true

sudo apt-get autoremove -y
sudo apt-get autoclean
docker system prune -af --volumes

sudo systemctl stop containerd || true
sudo rm -rf /var/lib/containerd/io.containerd.snapshotter.v1.overlayfs/snapshots/* || true
sudo systemctl start containerd || true

df -h /
