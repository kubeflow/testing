# Worker Images for Test and Release Workers

This directory contains the source for the docker images
that we use to run a bunch of our test and release scripts.

## To update the test worker images used in the Tekton tasks

1. Build a new image.

   ```
   skaffold build -p testing --kube-context=kubeflow-testing -v info --file-output=latest_image.json
   ```
1. Set the `kpt setter`

   ```
   kpt cfg set ./tekton test-image ${IMAGE}

   ```

## To build a release image

```
skaffold build -v info -p kf-releasing --file-output=latest_images.release.json

```

* This will only work if you have access to the release project