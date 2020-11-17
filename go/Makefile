build-prctl-image:
	skaffold build -p releasing --kube-context=kubeflow-releasing -v info --file-output=prctl_latest_image.json

build-cleanup-image:
	docker build -f Dockerfile.cleanup . -t gcr.io/kubeflow-images-public/cleanup:latest

run-cleanup:
	docker run -v ~/.kube/config:/root/.kube/config gcr.io/kubeflow-images-public/cleanup:dev-bobgy
