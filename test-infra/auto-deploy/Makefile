# Copyright 2017 The Kubernetes Authors.
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
#
# Requirements:
#   https://github.com/mattrobenolt/jinja2-cli
#   pip install jinja2-clie
IMG = gcr.io/kubeflow-ci/deploy-worker

# Whether to use cached images with GCB
USE_IMAGE_CACHE ?= true

TAG := $(shell date +v%Y%m%d)-$(shell git describe --tags --always --dirty)-$(shell git diff | shasum -a256 | cut -c -6)
DIR := ${CURDIR}

all: build

# To build without the cache set the environment variable
# export DOCKER_BUILD_OPTS=--no-cache
build:
	docker build ${DOCKER_BUILD_OPTS} -t $(IMG):$(TAG) .	
	@echo Built $(IMG):$(TAG)

# Build but don't attach the latest tag. This allows manual testing/inspection of the image
# first.
push: build
	gcloud docker -- push $(IMG):$(TAG)	
	@echo Pushed $(IMG):$(TAG)
	# Add tag starting hitting problems so tag and push
	docker tag $(IMG):$(TAG) $(IMG):latest
	gcloud docker -- push $(IMG):$(TAG) 	

build-gcb:
	gcloud builds submit --machine-type=n1-highcpu-32 --project=kubeflow-ci \
    --tag=$(IMG):$(TAG) \
	--timeout=3600
