OPTIONAL_TEST_INFRA_REPO_DIRS=./GitOps

#***************************************************************************************************

# Generate YAML files for Optional-Test-Infra GitOps
optional-generate:
	make optional-generate-kubeflow-shared-test-infra-poc
	make optional-generate-kubeflow-shared-test-infra-poc-argo
	make optional-generate-kubeflow-shared-test-infra-poc-tekton

# Generate YAML files for Optional-Test-Infra GitOps for kubeflow-shared-test-infra-poc cluster
optional-generate-kubeflow-shared-test-infra-poc:
	echo "Start generating yaml files for kubeflow-shared-test-infra-poc cluster"
	kubectl -n prow create configmap config \
	--from-file=config.yaml=./User/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/configmap/config.yaml \
	--dry-run=client -o yaml > \
	${OPTIONAL_TEST_INFRA_REPO_DIRS}/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/config.yaml
	kubectl -n prow create configmap plugins \
	--from-file=config.yaml=./User/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/configmap/plugins.yaml \
	--dry-run=client -o yaml > \
	${OPTIONAL_TEST_INFRA_REPO_DIRS}/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/plugins.yaml
	echo "Finish generating yaml files for kubeflow-shared-test-infra-poc cluster"

# Generate YAML files for Optional-Test-Infra GitOps for kubeflow-shared-test-infra-poc-argo cluster
optional-generate-kubeflow-shared-test-infra-poc-argo:
	echo "Start generating yaml files for kubeflow-shared-test-infra-poc-argo cluster"
	####
	# Add Logic to generate yaml files here
	####
	echo "Finish generating yaml files for kubeflow-shared-test-infra-poc-argo cluster"

# Generate YAML files for Optional-Test-Infra GitOps for kubeflow-shared-test-infra-poc-tekton cluster
optional-generate-kubeflow-shared-test-infra-poc-tekton:
	echo "Start generating yaml files for kubeflow-shared-test-infra-poc-tekton cluster"
	cp -r ./User/clusters/kubeflow-shared-test-infra-poc-tekton/namespaces/tekton-templates/pipelineresources/*.yaml \
	${OPTIONAL_TEST_INFRA_REPO_DIRS}/clusters/kubeflow-shared-test-infra-poc-tekton/namespaces/tekton-templates
	echo "Finish generating yaml files for kubeflow-shared-test-infra-poc-tekton cluster"



