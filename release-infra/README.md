
# Release Infrastructure

This page describes our release infrastructure.

It also contains various config files for our release instrastructure.

## IAM Policies

We manage IAM policies declaratively to create a versioned history of any changes.
Changes are not automatically applied; an appropriate owner needs to apply the changes.

To get the latest changes

```
gcloud projects get-iam-policy ${PROJECT} > ${PROJECT}.iam.policy.yaml
```

To change the IAM policy

1. Get the current etag by running

   ```
   gcloud projects get-iam-policy ${PROJECT} > ${PROJECT}.iam.policy.yaml
   ```

1. Create and submit a PR with the desired changes

1. Ask an admin to apply changes using 

   ```
   gcloud projects set-iam-policy ${PROJECT} ${PROJECT}.iam.policy.yaml
   ```

## Release infrastructure

Our release infrastructure is largely identical to our [test infrastructure](https://github.com/kubeflow/testing/blob/master/README.md)
except its more locked down.

In particular, we don't expose the Argo UI publicly.

Additionally we need to grant the service account access to the GCR
registry used to host our images.

```
GCR_PROJECT=kubeflow-images-public
gcloud projects add-iam-policy-binding ${GCR_PROJECT} \
      --member serviceAccount:${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com
      --role=roles/storage.admin
```

We also need to give access to the GCB service account to the registry

```
GCR_PROJECT=kubeflow-images-public
GCB_SERVICE_ACCOUNT=${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com
gcloud projects add-iam-policy-binding ${GCR_PROJECT} \
      --member serviceAccount:${GCB_SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com
      --role=roles/storage.admin
```
