# TODO(Bobgy): switch to the following once the PR is merged
# PACKAGE_URL=https://github.com/kubeflow/testing.git/gcp/packages/cluster-standard@master
PACKAGE_URL=https://github.com/Bobgy/testing.git/gcp/packages/cluster-standard@kfp_ci_deployment
export PROJECT=kubeflow-ci-deployment
export NAME=kfp-standalone-1

REPO_ROOT=../..
ACM_REPOS=$(REPO_ROOT)/acm-repos
NAMESPACE_DIR=$(ACM_REPOS)/kf-ci-management/namespaces/kubeflow-ci-deployment

hydrate: FORCE set-values
	kustomize build $(NAME) -o $(NAMESPACE_DIR)

get-pkg: FORCE
	rm -r $(NAME)
	kpt pkg get $(PACKAGE_URL) ./$(NAME)

set-values: FORCE
	cd $(NAME) && $(MAKE) set-values

# an empty rule forces other rules to always rerun
FORCE: ;
