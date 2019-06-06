# Admin infrastructure

Infrastructure used to administer our GitHub org and Gsuite domain.

This requires elevated permissions so it runs in a locked down project
and cluster.


## GKE Cluster

We can't use a private cluster since we need to access the GitHub APIs

```
gcloud --project=kubeflow-admin deployment-manager deployments create kf-admin-cluster --config=cluster.yaml --description="GKE cluster for administering GitHub and Gsuite Orgs."
```
