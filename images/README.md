# Worker Images for Test and Release Workers

This directory contains the source for the docker images
that we use to run a bunch of our test and release scripts.


## To build a release image

```
skaffold build -v info -p kf-releasing 
```

* This will only work if you have access to the release project