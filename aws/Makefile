OPTIONAL_TEST_INFRA_GITOPS_DIRS=./GitOps

#***************************************************************************************************

# Generate YAML files for Optional-Test-Infra GitOps
optional-generate:
	make optional-generate-kubeflow-shared-test-infra-poc
	make optional-generate-kubeflow-shared-test-infra-poc-argo
	make optional-generate-kubeflow-shared-test-infra-poc-tekton
	make optional-generate-optional-test-infra-prow
	make optional-generate-optional-test-infra-argo
	make optional-generate-optional-test-infra-tekton

# Validate if optional-generate runs
optional-test:
	rm -rf ./tmp
	mkdir ./tmp
	make optional-generate OPTIONAL_TEST_INFRA_GITOPS_DIRS=./tmp
	diff -x '*.md'  ./tmp ./GitOps
	rm -rf ./tmp

# Generate YAML files for Optional-Test-Infra GitOps for kubeflow-shared-test-infra-poc cluster
optional-generate-kubeflow-shared-test-infra-poc:
	echo ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}
	echo "Start generating yaml files for kubeflow-shared-test-infra-poc cluster"
	rm -rf ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/*
	mkdir -p ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/
	kubectl -n prow --kubeconfig=./testing/fake-kubeconfig/config.yaml create configmap config \
	--from-file=config.yaml=./User/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/configmap/config.yaml \
	--dry-run=client -o yaml > \
	${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/config.yaml
	kubectl -n prow --kubeconfig=./testing/fake-kubeconfig/config.yaml create configmap plugins \
	--from-file=plugins.yaml=./User/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/configmap/plugins.yaml \
	--dry-run=client -o yaml > \
	${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/plugins.yaml
	echo "Finish generating yaml files for kubeflow-shared-test-infra-poc cluster"

# Generate YAML files for Optional-Test-Infra GitOps for kubeflow-shared-test-infra-poc-argo cluster
optional-generate-kubeflow-shared-test-infra-poc-argo:
	echo ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}
	echo "Start generating yaml files for kubeflow-shared-test-infra-poc-argo cluster"
	rm -rf ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/kubeflow-shared-test-infra-poc-argo/namespaces/argo/*
	mkdir -p ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/kubeflow-shared-test-infra-poc-argo/namespaces/argo/
	####
	# Add Logic to copy yaml files here
	####
	echo "Finish generating yaml files for kubeflow-shared-test-infra-poc-argo cluster"

# Generate YAML files for Optional-Test-Infra GitOps for kubeflow-shared-test-infra-poc-tekton cluster
optional-generate-kubeflow-shared-test-infra-poc-tekton:
	echo ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}
	echo "Start generating yaml files for kubeflow-shared-test-infra-poc-tekton cluster"
	rm -rf ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/kubeflow-shared-test-infra-poc-tekton/namespaces/tekton-templates/*
	mkdir -p ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/kubeflow-shared-test-infra-poc-tekton/namespaces/tekton-templates/
	####
	# Add Logic to copy yaml files here
	####
	echo "Finish generating yaml files for kubeflow-shared-test-infra-poc-tekton cluster"

# Generate YAML files for Optional-Test-Infra GitOps for optional-test-infra-prow cluster
optional-generate-optional-test-infra-prow:
	echo ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}
	echo "Start generating yaml files for optional-test-infra-prow cluster"
	rm -rf ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/optional-test-infra-prow/namespaces/prow/*
	mkdir -p ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/optional-test-infra-prow/namespaces/prow/
	kubectl -n prow --kubeconfig=./testing/fake-kubeconfig/config.yaml create configmap config \
	--from-file=config.yaml=./User/clusters/optional-test-infra-prow/namespaces/prow/configmap/config.yaml \
	--dry-run=client -o yaml > \
	${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/optional-test-infra-prow/namespaces/prow/config.yaml
	kubectl -n prow --kubeconfig=./testing/fake-kubeconfig/config.yaml create configmap plugins \
	--from-file=plugins.yaml=./User/clusters/optional-test-infra-prow/namespaces/prow/configmap/plugins.yaml \
	--dry-run=client -o yaml > \
	${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/optional-test-infra-prow/namespaces/prow/plugins.yaml
	echo "Finish generating yaml files for optional-test-infra-prow cluster"

# Generate YAML files for Optional-Test-Infra GitOps for optional-test-infra-argo cluster
optional-generate-optional-test-infra-argo:
	echo ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}
	echo "Start generating yaml files for optional-test-infra-argo cluster"
	rm -rf ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/optional-test-infra-argo/namespaces/argo/*
	mkdir -p ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/optional-test-infra-argo/namespaces/argo/
	####
	# Add Logic to copy yaml files here
	####
	echo "Finish generating yaml files for optional-test-infra-argo cluster"

# Generate YAML files for Optional-Test-Infra GitOps for optional-test-infra-tekton cluster
optional-generate-optional-test-infra-tekton:
	echo ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}
	echo "Start generating yaml files for optional-test-infra-tekton cluster"
	rm -rf ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/optional-test-infra-tekton/namespaces/kubeflow-test-infra/*
	mkdir -p ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/optional-test-infra-tekton/namespaces/kubeflow-test-infra/
	cp -r ./User/clusters/optional-test-infra-tekton/namespaces/kubeflow-test-infra/task/ \
    ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/optional-test-infra-tekton/namespaces/kubeflow-test-infra/
	cp -r ./User/clusters/optional-test-infra-tekton/namespaces/kubeflow-test-infra/pipeline/ \
    ${OPTIONAL_TEST_INFRA_GITOPS_DIRS}/clusters/optional-test-infra-tekton/namespaces/kubeflow-test-infra/
	echo "Finish generating yaml files for optional-test-infra-tekton cluster"
