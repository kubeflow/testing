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
NAMESPACE_DIR=$(ACM_REPOS)/kf-ci-management/namespaces/kubeflow-ci-deployment

hydrate: FORCE set-values
	kustomize build $(NAME)/instance -o $(NAMESPACE_DIR)

get-pkg: FORCE
	kpt pkg get $(PACKAGE_URL) ./$(NAME)

update-pkg-upstream: FORCE
	rm -r $(NAME)/upstream
	kpt pkg get $(PACKAGE_UPSTEAM_URL) ./$(NAME)/upstream

set-values: FORCE
	cd $(NAME) && $(MAKE) set-values

# an empty rule forces other rules to always rerun
FORCE: ;
