REPO_URL=https://github.com/kubeflow/testing.git
GIT_REF=master
PACKAGE_URL=$(REPO_URL)/gcp/packages/cluster-standard@$(GIT_REF)
PACKAGE_UPSTEAM_URL=$(REPO_URL)/gcp/packages/cluster-standard/upstream@$(GIT_REF)

# This can be uncommented for development
# PACKAGE_URL=https://github.com/Bobgy/testing.git/gcp/packages/cluster-standard@branch

export PROJECT=kfp-ci
export NAME=kfp-standalone-1

REPO_ROOT=../..
ACM_REPOS=$(REPO_ROOT)/acm-repos
MGMT_DEPLOY_DIR=$(ACM_REPOS)/kf-ci-management/namespaces/$(PROJECT)
KFP_STANDALONE_1_DIR=$(ACM_REPOS)/kfp-standalone-1

# Please edit the following version before running:
# make kfp-update
PIPELINES_VERSION?=2.0.0-beta.1
PIPELINES_SRC_REPO=https://github.com/kubeflow/pipelines.git

all: hydrate hydrate-kfp-manifests vet-kfp-manifests

hydrate: FORCE set-values
	kustomize build $(NAME)/instance -o $(MGMT_DEPLOY_DIR)
	kustomize build $(NAME)/upstream/services -o $(MGMT_DEPLOY_DIR)
	cp iam/iam.yaml $(MGMT_DEPLOY_DIR)/

get-pkg: FORCE
	kpt pkg get $(PACKAGE_URL) ./$(NAME)

update-pkg-upstream: FORCE
	rm -rf $(NAME)/upstream
	cp -r $(REPO_ROOT)/gcp/packages/cluster-standard/upstream ./$(NAME)/
	# Or use the following to fetch from remote
	# kpt pkg get $(PACKAGE_UPSTEAM_URL) ./$(NAME)/upstream
	make set-values

set-values: FORCE
	kpt cfg set ./iam name "$(NAME)"
	cd $(NAME) && make set-values

apply-configsync: FORCE
	kubectl apply -k $(NAME)/configsync

status-configsync: FORCE
	nomos --contexts $(NAME) status

connect: FORCE
	kubectl config delete-context $(NAME) || echo "Not found"
	gcloud container clusters get-credentials $(NAME) --region us-central1 --project $(PROJECT)
	kubectl config rename-context $$(kubectl config current-context) $(NAME)

kfp-update: get-kfp-manifests hydrate-kfp-manifests FORCE

get-kfp-manifests: FORCE
	rm -rf $(NAME)/kustomize/upstream
	mkdir -p $(NAME)/kustomize
	kpt pkg get $(PIPELINES_SRC_REPO)/manifests/kustomize@$(PIPELINES_VERSION) $(NAME)/kustomize/upstream

hydrate-kfp-manifests: FORCE
	rm -rf $(KFP_STANDALONE_1_DIR)
	mkdir -p $(KFP_STANDALONE_1_DIR)
	kubectl kustomize $(NAME)/kustomize/instance > $(KFP_STANDALONE_1_DIR)/kfp-all.yaml

vet-kfp-manifests: FORCE
	nomos vet --path=$(KFP_STANDALONE_1_DIR) --source-format unstructured

get-kfp-endpoint: FORCE
	@kubectl describe configmap inverse-proxy-config -n kubeflow | grep .googleusercontent.com

# an empty rule forces other rules to always rerun
FORCE: ;
