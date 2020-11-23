ACM_REPO_DIR=../../../acm-repos/kf-ci-v1
AUTO_DEPLOY_CONTEXT=kf-ci-v1
NAMESPACE=cleanup
NAMESPACE_DIR=$(ACM_REPO_DIR)/namespaces/$(NAMESPACE)

.PHONY: hydrate
hydrate:
	# Remove old config maps.
	rm -rf $(NAMESPACE_DIR)
	mkdir -p $(NAMESPACE_DIR)
	cp ./namespace.yaml $(NAMESPACE_DIR)/
	kustomize build -o $(NAMESPACE_DIR)/ .
	kustomize build -o $(ACM_REPO_DIR)/cluster/ ./cluster

apply: hydrate
	kubectl --context=kf-ci-v1 apply -f $(ACM_REPO_DIR)/namespaces/$(NAMESPACE)
