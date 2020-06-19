# Worker Images for Test and Release Workers

This directory contains the source for the docker images
that we use to run a bunch of our test and release scripts.

## To update the test worker images used in the Tekton tasks

```
cd ..
make update-worker-image
```

## To build a release image

```
skaffold build -v info -p kf-releasing --file-output=latest_images.release.json

```

* This will only work if you have access to the release project