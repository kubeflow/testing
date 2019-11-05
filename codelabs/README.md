# Bulk Deploy Kubeflow On Codelab Test Projects

This directory contains tools for automatically deploying instances
of Kubeflow in codelab test projects.

The scripts are intended to run on a kubeflow cluster.

**project**: kf-codelab-admin
**cluster**: codelab-admin
**bucket**: gs://kf-codelab-admin
**OAuth location**: gs://kf-codelab-admin/test-project-iap.oauth.yaml
**GSA*: codelab-admin-user@kf-codelab-admin.iam.gserviceaccount.com


## Permissions

In order for to modify the codelab project you need to grant OWNER privileges to the GCP service
account used by the K8s job

* We use the GSA codelab-admin-user@kf-codelab-admin.iam.gserviceaccount.com
* Which is mapped to the default-editor KSA

## Instructions bulk setup of kubeflow codelab projects

1. Ensure the Google Sheet containing the code lab account has a field project

   * With the last batch of projects it looked like the convention was 

     ```
     USER=devstar${NUMBER}@gcplab.me
     PROJECT=kf-test-${NUMBER}
     ```

1. Export the Google Sheet containing the code lab accounts to CSV
1. Copy the CSV to `gs://kf-codelab-admin`

   ```
   DATE=$(date +%Y%m%d-%H%M%S)
   gsutil cp ${CSV_FILE} gs://kf-codelab-admin/test-project.${DATE}.csv
   ```

1. If necessary modify [setup-codelab-project.yaml](setup-codelab-project.yaml) to configure how each 
   Kubeflow instance will be considered.

   * This YAML file defines a K8s job which is used as a template for each K8s job that is created to setup a Kubeflow instance
   * This K8s job uses `kubeflow.testing.create_unique_kf_instance` to deploy Kubeflow
   * The arguments of `kubeflow.testing.create_unique_kf_instance` control how Kubeflow is deployed and you may want to change them
   * The most important parameters are

     * **kfname** The name of the Kubeflow deployment
     * **kfctl_path** The URL of the kfctl binry to use to deploy Kubeflow
       * Its also possible to build kfctl from a specific commit but that's slower
     * **kfctl_config** The URL of the KFDef manifest used for each deployment

1. Modify [bulk-deploy.yaml](bulk-yaml.yaml) to configure a K8s job to run bulk deployment

   * Set the following command line arguments in the YAML file

     * **projects_path** Change this to the path of the GCS file in the previous step

1. Launch a K8s job running bulk deploy

   ```
   kubectl create -f bulk-deploy.yaml
   ```

   * This job will launch one K8s job for each Kubeflow deployment
   * All of the launched K8s jobs will have the same value for the **group** label
   * The bulk-deploy job will wait for all of the jobs in the group to finish

1.  Run a K8s job to check whether each Kubeflow deployment has an endpoint that is accessible

    * Edit `test-codelab-endpoints.yaml`

      * Set **projects_path** to the GCS path of the CSV file containing your projects

    * Launch the job

      ```
      kubectl create -f test-codelab-endpoints.yaml
      ```

    * The job will print out which projects in the CSV file have accessible Kubeflow deployments
