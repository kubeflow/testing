REPO_DIRS=./acm-repos
AUTO_DEPLOY_CONTEXT=kf-ci-v1

#***************************************************************************************************

TEKTON_INSTALLS=./tekton/templates/installs
# Hydrate ACM repos
.PHONY: hydrate
hydrate:
	rm -f $(REPO_DIRS)/kf-ci-v1/namespaces/auto-deploy/tekton*	
	rm -f $(REPO_DIRS)/kf-ci-v1/namespaces/kf-ci/kf-ci
	kustomize build -o $(REPO_DIRS)/kf-ci-v1/namespaces/auto-deploy/auto-deploy.yaml test-infra/auto-deploy/manifest
	kustomize build -o $(REPO_DIRS)/kf-ci-v1/namespaces/auto-deploy $(TEKTON_INSTALLS)/auto-deploy
	kustomize build -o $(REPO_DIRS)/kf-ci-v1/namespaces/kf-ci $(TEKTON_INSTALLS)/kf-ci

