REPO_DIRS=../../acm-repos
AUTO_DEPLOY_CONTEXT=kf-ci-v1

.PHONY: hydrate
hydrate:
	rm $(REPO_DIRS)/kf-ci-v1/namespaces/auto-deploy/tekton*
	rm $(REPO_DIRS)/kf-ci-v1/namespaces/tektoncd/tekton*
	kustomize build -o $(REPO_DIRS)/kf-ci-v1/namespaces/auto-deploy ./installs/auto-deploy
	kustomize build -o $(REPO_DIRS)/kf-ci-v1/namespaces/tektoncd ./installs/tektoncd

