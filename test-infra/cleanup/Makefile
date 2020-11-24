ACM_REPO_DIR=../../acm-repos/kf-ci-v1
AUTO_DEPLOY_CONTEXT=kf-ci-v1

.PHONY: hydrate
hydrate:
	# Remove old config maps.
	rm -f $(ACM_REPO_DIR)/namespaces/auto-deploy/*v1_configmap_cleanup-config-*
	kustomize build -o $(ACM_REPO_DIR)/namespaces/auto-deploy ./

apply: hydrate
	kubectl --context=kf-ci-v1 -n auto-deploy apply -f $(ACM_REPO_DIR)/namespaces/auto-deploy
