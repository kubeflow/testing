# Architecture

This directory contains the architecture of Optional test Infrastructure for kubeflow community.

We use [Prow](https://github.com/kubernetes/test-infra/tree/master/prow),
K8s' continuous integration tool.

  * Prow is a set of binaries that run on Kubernetes and respond to
GitHub events.

We use Prow to run:

  * Presubmit jobs
  * Postsubmit jobs
  * Periodic tests

Here's how it works

  * Prow is used to trigger E2E tests
  * The E2E test will launch an Argo workflow / Tekton Pipelinerun that describes the tests to run
  * Each step in the Argo workflow or Each task in the Tekton Pipelinerun will be a binary invoked inside a container
  * The Argo workflow will use an NFS volume to attach a shared POSIX compliant filesystem to each step in the
    workflow.
    * Each step in the pipeline can write outputs and junit.xml files to a test directory in the volume
  * A final step in the Argo pipeline / Tekton Pipelinerun will upload the outputs to S3 so they are available in spyglass

Quick Links

  * [Argo UI](http://86308603-argo-argo-5ce9-1162466691.us-west-2.elb.amazonaws.com/)
  * [Prow Dashboard](http://8069b97e-prow-prow-6530-1439048706.us-west-2.elb.amazonaws.com/)
  
## Anatomy of our Tests

* Our prow jobs are defined [here](https://github.com/kubeflow/testing/tree/master/aws/User/clusters/kubeflow-shared-test-infra-poc/namespaces/prow/configmap/config.yaml)
* Each prow job defines a K8s PodSpec indicating a command to run
* Our prow jobs use [run_e2e_workflow.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/run_e2e_workflow.py)
  to trigger an Argo workflow / Tekton Pipelinerun that checks out our code and runs our tests.
* Our tests are structured as Argo workflows / Tekton Pipelinerun so that we can easily perform steps in parallel.
* The Argo workflow / Tekton Pipelinerun is defined in the repository being tested
* [checkout.sh](https://github.com/kubeflow/testing/blob/master/images/checkout.sh) is used to checkout the code being tested
   * This also checks out [kubeflow/testing](https://github.com/kubeflow/testing/) so that all repositories can
     rely on it for shared tools.
     
## Diagram of Architecture

* [Current Design](https://github.com/kubeflow/testing/tree/master/aws/Picture/OptionalTestInfra_CurrentDesign.png)
* [Future Design](https://github.com/kubeflow/testing/tree/master/aws/Picture/OptionalTestInfra_FutureDesign.png)
