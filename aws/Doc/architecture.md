# Architecture

This directory contains the architecture of Optional test infrastructure for kubeflow community.

We use [Prow](https://github.com/kubernetes/test-infra/tree/master/prow), K8s' continuous integration tool.

  * Prow is a set of binaries that run on Kubernetes and respond to GitHub events.

We use Prow to run:

  * Presubmit jobs
  * Postsubmit jobs
  * Periodic tests

Here's high-level idea how it works

* Our prow jobs are defined [here](https://github.com/kubeflow/testing/tree/master/aws/User/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/configmap/config.yaml)
    * Define Presubmit tests in the [presubmits section](https://github.com/kubeflow/testing/blob/master/aws/User/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/configmap/config.yaml#L118)
    * Define Periodic tests in the [periodics section](https://github.com/kubeflow/testing/blob/master/aws/User/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/configmap/config.yaml#L79)
    * [TODO] Define Postsubmit tests after shipment of public ECR support.
* Each prow job defines a K8s PodSpec indicating a command to run, pod details:
    * Container image `527798164940.dkr.ecr.us-west-2.amazonaws.com/aws-kubeflow-ci/test-worker:v1.2-branch`, image's dockerfile can be found [here](https://github.com/kubeflow/testing/blob/master/images/Dockerfile.py3.aws)
    * Entry-point is `/usr/local/bin/run_workflows.sh`, details can be found [here](https://github.com/kubeflow/testing/blob/master/images/run_workflows.sh)
    * Pre-defined [environment variables](https://github.com/kubeflow/testing/blob/master/aws/User/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/configmap/config.yaml#L93-L98)
* Our prow jobs use [run_e2e_workflow.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/run_e2e_workflow.py)
  to trigger an Argo workflow / Tekton Pipelinerun that checks out our code and runs our tests.
    * run_e2e_workflow.py will invoke repo's `prow_config.yaml` file, e.g, [kubeflow/manifests](https://github.com/kubeflow/manifests/blob/master/prow_config.yaml)
    * Then it will generate argo workflow with pre-defined logic in the kubeflow repo, e.g, [kubeflow/kfctl](https://github.com/kubeflow/kfctl/blob/master/py/kubeflow/kfctl/testing/ci/kfctl_e2e_workflow.py)
    * After generation, prow send generated objects to remote Argo cluster or Tekton cluster and kick off workflow running
    
   Note: Our tests are structured as Argo workflows / Tekton Pipelinerun so that we can easily perform steps in parallel
* Prow keep an async HTTP connection with Argo / Tekton cluster for workflow/pipelinerun's status (`Failed / Succeeded / Running`)
  * If test status becomes a determined stage (`Failed / Succeeded`), prow break the connection and send status back to GitHub
  * If test status stays with `Running`, prow will periodically send request for test status

## Diagram of Architecture

* [Current Design](https://github.com/kubeflow/testing/tree/master/aws/Picture/OptionalTestInfra_CurrentDesign.png)
* [Future Design](https://github.com/kubeflow/testing/tree/master/aws/Picture/OptionalTestInfra_FutureDesign.png)
