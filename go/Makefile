build-prctl-image:
	skaffold build -p releasing --kube-context=kubeflow-releasing -v info --file-output=prctl_latest_image.json

build-cleanup-image:
	docker build -f Dockerfile.cleanup . -t gcr.io/kubeflow-ci/cleanup:latest

push-cleanup-image:
	docker push gcr.io/kubeflow-ci/cleanup:latest

run-cleanup:
	docker run -v ~/.kube/config:/root/.kube/config gcr.io/kubeflow-ci/cleanup:latest
