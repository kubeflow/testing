# Auto Deploy Playbook

Playbook for the auto deployed instances of Kubeflow.


## Check the reconciler

1. Check logs

   * [Reconciler logs](https://console.cloud.google.com/logs/viewer?project=kubeflow-ci&folder&organizationId&minLogLevel=0&expandAll=false&interval=PT1H&resource=k8s_container%2Fcluster_name%2Fkubeflow-testing%2Fnamespace_name%2Ftest-pod&advancedFilter=resource.type%3D%22k8s_container%22%0Aresource.labels.cluster_name%3D%22kf-ci-v1%22%0Aresource.labels.namespace_name%3D%22auto-deploy%22%0Alabels.%22k8s-pod%2Fapp%22%3D%22auto-deploy%22%0Aresource.labels.container_name%3D%22reconciler%22)

     * You can filter by version name to see entries for a specific version; e.g

       ```
       resource.type="k8s_container"
       resource.labels.cluster_name="kf-ci-v1"
       resource.labels.namespace_name="auto-deploy"
       labels."k8s-pod/app"="auto-deploy"
       resource.labels.container_name="reconciler"
       jsonPayload.version_name="v1"
       ```

   * [Server logs](https://console.cloud.google.com/logs/viewer?project=kubeflow-ci&folder&organizationId&minLogLevel=0&expandAll=false&interval=PT1H&resource=k8s_container%2Fcluster_name%2Fkubeflow-testing%2Fnamespace_name%2Ftest-pod&advancedFilter=resource.type%3D%22k8s_container%22%0Aresource.labels.cluster_name%3D%22kf-ci-v1%22%0Aresource.labels.namespace_name%3D%22auto-deploy%22%0Alabels.%22k8s-pod%2Fapp%22%3D%22auto-deploy%22%0Aresource.labels.container_name%3D%22server%22)

1. Connect to the **kf-ci-v1** cluster
1. Get the most recent auto deploy jobs

   ```
   kubectl -n auto-deploy get jobs --sort-by=".metadata.creationTimestamp"
   ```

   * fetch those logs
   * Go to the [GKE Workloads Dashboard](https://cloud.console.google.com/kubernetes/workload?project=kubeflow-ci&pageState=(%22workload_list_table%22:(%22f%22:%22%255B%257B_22k_22_3A_22Is%2520system%2520object_22_2C_22t_22_3A11_2C_22v_22_3A_22_5C_22False_~*false_5C_22_22_2C_22i_22_3A_22is_system_22%257D_2C%257B_22k_22_3A_22cluster_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22kf-ci-v1_5C_22_22_2C_22s_22_3Atrue_2C_22i_22_3A_22metadata%252FclusterReference%252Fname_22%257D_2C%257B_22k_22_3A_22namespace_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22auto-deploy_5C_22_22_2C_22s_22_3Atrue_2C_22i_22_3A_22metadata%252Fnamespace_22%257D%255D%22) and navigate to the job
   	  * Click through to the pod and then the link to view the logs
      * TODO(jlewi): Unfortunately the dashboard doesn't appear to allow sorting by
        creation timestamp which makes it hard to find latest ones
