# TODO(Bobgy): restore to master
# REPO_URL=https://github.com/kubeflow/testing.git
# GIT_REF=master
REPO_URL=https://github.com/Bobgy/testing.git
GIT_REF=kfp_nodepool_size
PACKAGE_URL=$(REPO_URL)/gcp/packages/cluster-standard@$(GIT_REF)
PACKAGE_UPSTEAM_URL=$(REPO_URL)/gcp/packages/cluster-standard/upstream@$(GIT_REF)

# This can be uncommented for development
# PACKAGE_URL=https://github.com/Bobgy/testing.git/gcp/packages/cluster-standard@branch

export PROJECT=kubeflow-ci-deployment
export NAME=kfp-standalone-1

REPO_ROOT=../..
ACM_REPOS=$(REPO_ROOT)/acm-repos
MGMT_DEPLOY_DIR=$(ACM_REPOS)/kf-ci-management/namespaces/kubeflow-ci-deployment
KFP_STANDALONE_1_DIR=$(ACM_REPOS)/kfp-standalone-1

# Please edit the following version before running the script to pull new
# pipelines version.
PIPELINES_VERSION=1.1.1-beta.1
PIPELINES_SRC_REPO=https://github.com/kubeflow/pipelines.git

all: hydrate hydrate-kfp-manifests vet-kfp-manifests

hydrate: FORCE set-values
	kustomize build $(NAME)/instance -o $(MGMT_DEPLOY_DIR)

get-pkg: FORCE
	kpt pkg get $(PACKAGE_URL) ./$(NAME)

update-pkg-upstream: FORCE
	rm -r $(NAME)/upstream
	kpt pkg get $(PACKAGE_UPSTEAM_URL) ./$(NAME)/upstream
	$(MAKE) set-values

set-values: FORCE
	cd $(NAME) && $(MAKE) set-values

apply-configsync: FORCE
	kubectl apply -k $(NAME)/configsync

status-configsync: FORCE
	nomos --contexts $(NAME) status

connect: FORCE
	kubectl config delete-context $(NAME) || echo "Not found"
	gcloud container clusters get-credentials $(NAME) --region us-central1 --project kubeflow-ci-deployment
	kubectl config rename-context $$(kubectl config current-context) $(NAME)

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
	kubectl describe configmap inverse-proxy-config -n kubeflow | grep .pipelines.googleusercontent.com

# an empty rule forces other rules to always rerun
FORCE: ;
