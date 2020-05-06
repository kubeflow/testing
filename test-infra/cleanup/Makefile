ACM_REPO_DIR=../../acm-repo
AUTO_DEPLOY_CONTEXT=kf-ci-v1

.PHONY: hydrate
hydrate:	
	# Remove old config maps.
	rm -f $(ACM_REPO_DIR)/namespaces/auto-deploy/~g_v1_configmap_cleanup-config-*
	kustomize build -o $(ACM_REPO_DIR)/namespaces/auto-deploy ./

apply: hydrate	
	kubectl --context=kf-ci-v1 -n auto-deploy apply -f ../../acm-repo/namespaces/auto-deploy
