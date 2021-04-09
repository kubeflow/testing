DEPLOYMENT=kf-ci-v1
PROJECT_ARG=--project kubeflow-ci

# Refer to documentation:
# https://cloud.google.com/deployment-manager/docs/deployments/updating-deployments

.PHONY: list apply

list:
	gcloud deployment-manager deployments list $(PROJECT_ARG)

get:
	gcloud deployment-manager deployments describe $(DEPLOYMENT) $(PROJECT_ARG)

preview:
	gcloud deployment-manager deployments update $(DEPLOYMENT) $(PROJECT_ARG) \
		--config cluster-kubeflow.yaml \
		--preview

apply-preview:
	gcloud deployment-manager deployments update $(DEPLOYMENT) $(PROJECT_ARG)

apply:
	gcloud deployment-manager deployments update $(DEPLOYMENT) $(PROJECT_ARG) \
		--config cluster-kubeflow.yaml

cancel:
	gcloud deployment-manager deployments cancel-preview $(DEPLOYMENT) $(PROJECT_ARG)

stop:
	gcloud deployment-manager deployments stop $(DEPLOYMENT) $(PROJECT_ARG)
