REPO_DIRS=./acm-repos
AUTO_DEPLOY_CONTEXT=kf-ci-v1
KFCI_CONTEXT=kf-ci-v1

#***************************************************************************************************

TEKTON_INSTALLS=./tekton/templates/installs

.PHONY: all
all: hydrate acm-test

# Hydrate ACM repos
.PHONY: hydrate
hydrate:
	find $(REPO_DIRS)/kf-ci-v1/namespaces/auto-deploy -type f -not -name namespace.yaml -exec rm {} ";"
	rm -f $(REPO_DIRS)/kf-ci-v1/namespaces/auto-deploy/tekton*
	find $(REPO_DIRS)/kf-ci-v1/namespaces/kf-ci -type f -not -name namespace.yaml -o -name service-account-kf-ci.yaml -exec rm {} ";"
	find $(REPO_DIRS)/kf-ci-management/namespaces/kfp-ci -type f -not -name namespace.yaml -exec rm {} ";"
	rm -rf $(REPO_DIRS)/kf-ci-v1/namespaces/test-pods
	mkdir -p $(REPO_DIRS)/kf-ci-v1/namespaces/test-pods

	kustomize build -o $(REPO_DIRS)/kf-ci-v1/namespaces/auto-deploy $(TEKTON_INSTALLS)/auto-deploy
	kustomize build -o $(REPO_DIRS)/kf-ci-v1/namespaces/auto-deploy test-infra/auto-deploy/manifest
	kustomize build -o $(REPO_DIRS)/kf-ci-v1/namespaces/kf-ci $(TEKTON_INSTALLS)/kf-ci
	kustomize build -o $(REPO_DIRS)/kf-ci-v1/namespaces/test-pods test-infra/kf-ci-v1/test-pods
	cp test-infra/kf-ci-v1/test-pods/namespace.yaml $(REPO_DIRS)/kf-ci-v1/namespaces/test-pods/
	cd test-infra/cleanup && $(MAKE) hydrate
	cd test-infra/kfp && make all

# Make sure there are no nomos errors
.PHONY: acm-test
acm-test:
	nomos vet --no-api-server-check --path=acm-repos/kf-ci-management
	nomos vet --no-api-server-check --path=acm-repos/kf-ci-v1

.PHONY: acm-status
acm-status:
	nomos status --contexts=kf-ci-management,kfp-standalone-1

# This applies your local changes to tekton components to the kf-ci-dev namespace.
# This allows you to test changes manually before your pipelines are submitted.
apply-kf-ci-dev:
	kustomize build $(TEKTON_INSTALLS)/kf-ci-dev | kubectl --context=$(KFCI_CONTEXT) apply -f -

build-worker-image:
	cd images && skaffold build -p testing --kube-context=kubeflow-testing -v info --file-output=latest_image.json

set-worker-image:
	kpt cfg set ./tekton test-image $(shell yq r ./images/latest_image.json builds[0].tag)

update-worker-image: build-worker-image set-worker-image

# This is a debug rule providing some sugar to hydrate and push the manifests and then wait for the
# sync
debug-push-and-run:
	make hydrate && git add . && git commit -m "Latest" && git push jlewi
	cd ./go/cmd/nomos-wait && go run .
	kubectl --context=kf-ci-v1 create -f ./tekton/runs/nb-test-run.yaml

# This is a debug rule providing some sugar for fast iteration during development
# It might need to be customized for your usage.
# make-update-worker-image builds and sets a new worker image.
# make hydrate ... rehydrates and pushes the Tekton resources
# nomos-wait waits for the latest nomos changes to be sync'd
# and then we submit a run of the pipeline.
debug-rebuild-and-run:
	make update-worker-image
	make hydrate && git add . && git commit -m "Latest" && git push jlewi
	cd ./go/cmd/nomos-wait && go run .
	kubectl --context=kf-ci-v1 create -f ./tekton/runs/nb-test-run.yaml
