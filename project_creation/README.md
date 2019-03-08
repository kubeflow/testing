# Creating Projects Through Deployment Manager

This folder contains configurations to create a new GCP project for deploying Kubeflow via Deployment Manager.

The files are modified based on [the example of GCP Deployment Manager](https://github.com/GoogleCloudPlatform/deploymentmanager-samples/tree/master/examples/v2/project_creation).

Project [kf-gcp-deploy0](https://pantheon.corp.google.com/kubernetes/workload?project=kf-gcp-deploy0&organizationId=714441643818) creates and owns the new projects, which are all in folder [gcp-deploy](https://pantheon.corp.google.com/projectselector2/kubernetes/list?folder=838562927550&supportedpurview=project)

# Command to create a project
Active service account. `<path/to/key-file>` points to the key file of 459682233032@cloudservices.gserviceaccount.com under kf-gcp-deploy0.
```
$ gcloud auth activate-service-account --key-file=<path/to/key-file>
```
Change the project name in `config.yaml` and run
```
$ gcloud deployment-manager --project=kf-gcp-deploy0 deployments create <DEPLOYMENT_NAME> --config config.yaml
```
