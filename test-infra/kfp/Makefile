PACKAGE_URL=https://github.com/kubeflow/testing.git/gcp/packages/cluster-standard@master

# This can be uncommented for development
# PACKAGE_URL=https://github.com/Bobgy/testing.git/gcp/packages/cluster-standard@branch

export PROJECT=kubeflow-ci-deployment
export NAME=kfp-standalone-1

REPO_ROOT=../..
ACM_REPOS=$(REPO_ROOT)/acm-repos
NAMESPACE_DIR=$(ACM_REPOS)/kf-ci-management/namespaces/kubeflow-ci-deployment

hydrate: FORCE set-values
	kustomize build $(NAME) -o $(NAMESPACE_DIR)

get-pkg: FORCE
	rm -r $(NAME)/upstream
	kpt pkg get $(PACKAGE_URL) ./$(NAME)/upstream

set-values: FORCE
	cd $(NAME) && $(MAKE) set-values

# an empty rule forces other rules to always rerun
FORCE: ;
