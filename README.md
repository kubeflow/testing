<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Test Infrastructure](#test-infrastructure)
  - [Anatomy of our Tests](#anatomy-of-our-tests)
  - [Writing An Argo Workflow For An E2E Test](#writing-an-argo-workflow-for-an-e2e-test)
    - [Adding an E2E test to a repository](#adding-an-e2e-test-to-a-repository)
      - [Python function](#python-function)
      - [ksonnet](#ksonnet)
    - [Using pytest to write tests](#using-pytest-to-write-tests)
    - [Prow Variables](#prow-variables)
    - [Argo Spec](#argo-spec)
    - [Creating K8s resources in tests.](#creating-k8s-resources-in-tests)
    - [NFS Directory](#nfs-directory)
    - [Step Image](#step-image)
    - [Checking out code](#checking-out-code)
    - [Building Docker Images](#building-docker-images)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Test Infrastructure

There are two test infrastructures exist in the Kubeflow community:  
  * [GoogleCloudPlatform/oss-test-infra](https://github.com/GoogleCloudPlatform/oss-test-infra)   
  * [AWS/optional-test-infra](https://github.com/kubeflow/testing/tree/master/aws)

If you are interested in **oss-test-infra**, please find useful resources [here](https://github.com/kubeflow/testing/tree/master/gcp_README.md).  
If you are interested in **optional-test-infra**, please find useful resources [here](https://github.com/kubeflow/testing/tree/master/aws/README.md)

We use [Prow](https://github.com/kubernetes/test-infra/tree/master/prow),
K8s' continuous integration tool.

  * Prow is a set of binaries that run on Kubernetes and respond to GitHub events.

We use Prow to run:

  * Presubmit jobs
  * Postsubmit jobs
  * Periodic tests

Here's high-level idea about how it works

  * Prow is used to trigger E2E tests
  * The E2E test will launch an Argo workflow that describes the tests to run
  * Each step in the Argo workflow will be a binary invoked inside a container
  * The Argo workflow will use an NFS volume to attach a shared POSIX compliant filesystem to each step in the
    workflow.
  * Each step in the pipeline can write outputs and junit.xml files to a test directory in the volume
  * A final step in the Argo pipeline will upload the outputs to GCS so they are available in spyglass
 
Quick Links

  * [Argo UI](http://testing-argo.kubeflow.org/)
  * [Test Grid](https://k8s-testgrid.appspot.com/sig-big-data)
  * [Prow jobs for kubeflow/kubeflow](https://prow.k8s.io/?repo=kubeflow%2Fkubeflow)

## Anatomy of our Tests

* Our prow jobs are defined [here](https://github.com/kubernetes/test-infra/tree/master/config/jobs/kubeflow)
* Each prow job defines a K8s PodSpec indicating a command to run
* Our prow jobs use [run_e2e_workflow.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/run_e2e_workflow.py)
  to trigger an Argo workflow that checks out our code and runs our tests.
* Our tests are structured as Argo workflows so that we can easily perform steps in parallel.
* The Argo workflow is defined in the repository being tested
   * We always use the worfklow at the commit being tested
* [checkout.sh](https://github.com/kubeflow/testing/blob/master/images/checkout.sh) is used to checkout the code being tested
   * This also checks out [kubeflow/testing](https://github.com/kubeflow/testing/) so that all repositories can
     rely on it for shared tools.

## Writing An Argo Workflow For An E2E Test

This section provides guidelines for writing Argo workflows to use as E2E tests

This guide is complementary to the [E2E testing guide for TFJob operator](https://github.com/kubeflow/tf-operator/blob/master/e2e_testing.md)
which describes how to author tests to performed as individual steps in the workflow.

Some examples to look at

  * [gis.jsonnet](https://github.com/kubeflow/examples/blob/master/test/workflows/components/gis.jsonnet) in kubeflow/examples


### Adding an E2E test to a repository

Follow these steps to add a new test to a repository.

#### Python function

1. Create a Python function in that repository and return an Argo workflow if one doesn't already exist
   * We use Python functions defined in each repository to define the Argo workflows corresponding to E2E tests

   * You can look at `prow_config.yaml` (see below) to see which Python functions are already defined in a repository.

1. Modify the `prow_config.yaml` at the root of the repo to trigger your new test.

   * If `prow_config.yaml` doesn't exist (e.g. the repository is new) copy one from an existing repository ([example](https://github.com/kubeflow/kubeflow/blob/master/prow_config.yaml)).

   * `prow_config.yaml` contains an array of workflows where each workflow defines an E2E test to run; example

       ```
       workflows:
        - name: workflow-test
          py_func: my_test_package.my_test_module.my_test_workflow
          kwargs:
              arg1: argument
       ```

       * **py_func**: Is the Python method to create a python object representing the Argo workflow resource
       * **kwargs**: This is an array of arguments passed to the Python method
       * **name**: This is the base name to use for the submitted Argo workflow.


1. You can use the [e2e_tool.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/e2e_tool.py) to print out the Argo workflow and potentially submit it

1. Examples

   * [kf_unittests.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/ci/kf_unittests.py)
      creates the E2E workflow for kubeflow/testing

#### ksonnet

** Using ksonnet is deprecated. New pipelines should use python. **
1. Create a ksonnet App in that repository and define an Argo workflow if one doesn't already exist
   * We use ksonnet apps defined in each repository to define the Argo workflows corresponding to E2E tests
   * If a ksonnet app already exists you can just define a new component in that app

     1. Create a .jsonnet file (e.g by copying an existing .jsonnet file)

        * Change the import for the params to use the newly defined component

        * See [gis.jsonnet in kubeflow/examples#449](https://github.com/kubeflow/examples/blob/d99abc23d10851fe8f3a19732ab5078f5edc0397/test/workflows/components/gis.jsonnet)

     1. Update the `params.libsonnet` to add a stanza to define params for the new component

       * See [params.jsonnet in kubeflow/examples#449](https://github.com/kubeflow/examples/blob/d99abc23d10851fe8f3a19732ab5078f5edc0397/test/workflows/components/params.libsonnet)

   * You can look at `prow_config.yaml` (see below) to see which ksonnet apps are already defined in a repository.

1. Modify the `prow_config.yaml` at the root of the repo to trigger your new test.

   * If `prow_config.yaml` doesn't exist (e.g. the repository is new) copy one from an existing repository ([example](https://github.com/kubeflow/kubeflow/blob/master/prow_config.yaml)).
     
   * `prow_config.yaml` contains an array of workflows where each workflow defines an E2E test to run; example

       ```
       workflows:
        - app_dir: kubeflow/testing/workflows
          component: workflows
          name: unittests
          job_types:
            - presubmit
          include_dirs:
            - foo/*
            - bar/*
              params:
          params:
            platform: gke
            gkeApiVersion: v1beta1
       ```

       * **app_dir**: Is the path to the ksonnet directory within the repository. This should be of the form `${GITHUB_ORG}/${GITHUB_REPO_NAME}/${PATH_WITHIN_REPO_TO_KS_APP}`
       * **component**: This is the name of the ksonnet component to use for the Argo workflow
       * **name**: This is the base name to use for the submitted Argo workflow.         

         * The test infrastructure appends a suffix of 22 characters (see [here](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/run_e2e_workflow.py#L196))
         
         * The result is passed to your ksonnet component via the name parameter

         * Your ksonnet component should truncate the name if necessary to satisfy
           K8s naming constraints.

           * e.g. Argo workflow names should be less than 63 characters because
             they are used as pod labels

       * **job_types**: This is an array specifying for which types of [prow jobs](https://github.com/kubernetes/test-infra/blob/master/prow/jobs.md)
          this workflow should be triggered on.

          * Currently allowed values are **presubmit**, **postsubmit**, and **periodic**.

      * **include_dirs**: If specified, the pre and postsubmit jobs will only trigger this test if the PR changed at least one file matching at least one
         of the listed directories.

         * Python's [fnmatch function](https://docs.python.org/2/library/fnmatch.html) is used to compare the listed patterns against the full path
           of modified files (see [here](https://github.com/kubeflow/testing/blob/46c5d0daa6d161e52f61b8fcaa448870945bea6d/py/kubeflow/testing/run_e2e_workflow.py#L181))

         * This functionality should be used to ensure that expensive tests are only run when test impacting changes are made; particularly if its an expensive or flaky presubmit

         * periodic runs ignore **include_dirs**; a periodic run will trigger all
           workflows that include job_type **periodic**

      * A given ksonnet component can have multiple workflow entries to allow different
        triggering conditions on pre/postsubmit

        * For example, on presubmit we might run a test on a single platform (GKE) but on
          postsubmit that same test might run on GKE and minikube
        * this can be accomplished with different entries pointing at the same ksonnet
          component but with different `job_types` and `params`.

     * **params**: A dictionary of parameters to set on the ksonnet component e.g. by running `ks param set ${COMPONENT} ${PARAM_NAME} ${PARAM_VALUE}`


### Using pytest to write tests

* [pytest](https://docs.pytest.org/en/latest/) is really useful for writing tests

   * Results can be emitted as junit files which is what prow needs to report test results
   * It provides [annotations](http://doc.pytest.org/en/latest/skipping.html) to skip tests or mark flaky tests as expected to fail

* Use pytest to easily script various checks

  * For example [kf_is_ready_test.py](https://github.com/kubeflow/kubeflow/blob/master/testing/kfctl/kf_is_ready_test.py)
    uses some simple scripting to test that various K8s objects are deployed and healthy

* Pytest provides fixtures for setting additional attributes in the junit files ([docs](http://doc.pytest.org/en/latest/usage.html))

  * In particular [record_xml_attribute](http://doc.pytest.org/en/latest/usage.html#record-xml-attribute) allows us to set attributes
    that control how's the results are grouped in test grid

    * **name** - This is the name shown in test grid

      * Testgrid supports [grouping](https://github.com/kubernetes/test-infra/tree/master/testgrid#grouping-tests) by spliting the tests into a hierarchy based on the name

      * **recommendation** Leverage this feature to name tests to support grouping; e.g. use the pattern

        ```
        {WORKFLOW_NAME}/{PY_FUNC_NAME}
        ```

        * **workflow_name** Workflow name as set in prow_config.yaml
        * **PY_FUNC_NAME** the name of the python test function

        * util.py provides the helper method `set_pytest_junit` to set the required attributes
        * run_e2e_workflow.py will pass the argument `test_target_name` to your py function to create the Argo workflow

          * Use this argument to set the environment variable **TEST_TARGET_NAME** on all Argo pods.

    * **classname** - testgrid uses **classname** as the test target and allows results to be grouped by name

      * **recommendation** - Set the classname to the workflow name as defined in **prow_config.yaml**

        * This allows easy grouping of tests by the entries defined in **prow_config.yaml**

        * Each entry in **prow_config.yaml** usually corresponds to a different configuration e.g. "GCP with IAP" vs. "GCP with basic auth"

        * So worflow name is a natural grouping    
    

### Prow Variables

* For each test run PROW defines several variables that pass useful information to your job.

* The list of variables is defined [in the prow docs](https://github.com/kubernetes/test-infra/blob/master/prow/jobs.md#job-environment-variables).

* These variables are often used to assign unique names to each test run to ensure isolation (e.g. by appending the BUILD_NUMBER)

* The prow variables are passed via ksonnet parameter `prow_env` to your workflows

  * You can copy the macros defined in [util.libsonnet](https://github.com/kubeflow/examples/blob/70a22d6d7bbb8bf126cc581d89d6cf40937e07f5/test/workflows/components/util.libsonnet#L30)
    to parse the ksonnet parameter into a jsonnet map that can be used in your workflow.

  * **Important** Always define defaults for the prow variables in the dict e.g. like

    ```
    local prowDict = {
      BUILD_ID: "notset",
      BUILD_NUMBER: "notset",
      REPO_OWNER: "notset",
      REPO_NAME: "notset",
      JOB_NAME: "notset",
      JOB_TYPE: "notset",
      PULL_NUMBER: "notset",  
     } + util.listOfDictToMap(prowEnv);
    ```

    * This prevents jsonnet from failing in a hard to debug way in the event that you try to access a key which is not in the map.

### Argo Spec

* Guard against long names by truncating the name and using the BUILD_ID to ensure the
  name remains unique e.g

  ```
  local name = std.substr(params.name, 0, std.min(58, std.lenght(params.name))) + "-" + prowDict["BUILD_ID"];            
  ```

  * Argo workflow names need to be less than 63 characters because they are used as pod 
    labels

  * BUILD_ID are unique for each run per repo; we suggest reserving 5 characters for
    the BUILD_ID.

* Argo workflows should have standard labels corresponding to prow variables; for example

  ```
  labels: prowDict + {    
    workflow_template: "code_search",    
  },
  ```

  * This makes it easy to query for Argo workflows based on prow job info.
  * In addition the convention is to use the following labels

    * **workflow_template**: The name of the ksonnet component from which the workflow is created.

* The templates for the individual steps in the argo workflow should also have standard labels

  ```
  labels: prowDict + {
    step_name: stepName,
    workflow_template: "code_search",
    workflow: workflowName,
  },
  ```

  * **step_name**: Name of the step (e.g. what shows up in the Argo graph)
  * **workflow_template**: The name of the ksonnet component from which the workflow is created.
  * **workflow**: The name of the Argo workflow that owns this pod.


* Following the above conventions make it very easy to get logs for specific steps

  ```
  kubectl logs -l step_name=checkout,REPO_OWNER=kubeflow,REPO_NAME=examples,BUILD_ID=0104-064201 -c main

  ```

### Creating K8s resources in tests.

Tests often need a K8s/Kubeflow deployment on which to create resources and run various tests.

Depending on the change being tested

  * The test might need exclusive access to a Kubeflow/Kubernetes cluster

    * e.g. Testing a change to a custom resource usually requires exclusive access to a K8s cluster 
      because only one CRD and controller can be installed per cluster. So trying to test two different
      changes to an operator (e.g. tf-operator) on the same cluster is not good.

  * The test might need a Kubeflow/K8s deployment but doesn't need exclusive access

    * e.g. When running tests for Kubeflow examples we can isolate each test using namespaces or
      other mechanisms.

* If the test needs exclusive access to the Kubernetes cluster then there should be a step in the workflow 
  that creates a KubeConfig file to talk to the cluster.

  * e.g. E2E tests for most operators should probably spin up a new Kubeflow cluster

* If the test just needs a known version of Kubeflow (e.g. master or v0.4) then it should use
  one of the test clusters in project kubeflow-ci for this

  * The infrasture to support this is not fully implemented see [kubeflow/testing#95](https://github.com/kubeflow/testing/issues/95)
    and [kubeflow/testing#273](https://github.com/kubeflow/testing/issues/273)


To connect to the cluster:
  * The Argo workflow should have a step that configures the `KUBE_CONFIG` file to talk to the cluster

    * e.g. by running `gcloud container clusters get-credentials`

  * The Kubeconfig file should be stored in the NFS test directory so it can be used in subsequent steps
  * Set the environment variable `KUBE_CONFIG` on your steps to use the KubeConfig file

### NFS Directory

An NFS volume is used to create a shared filesystem between steps in the workflow.

* Your Argo workflows should use a PVC claim to mount the NFS filesystem into each step

  * The current PVC name is `nfs-external`
  * This should be a parameter to allow different PVC names in different environments.

* Use the following directory structure 

  ```
  ${MOUNT_POINT}/${WORKFLOW_NAME}
                                 /src
                                     /${REPO_ORG}/${REPO_NAME}
                                 /outputs
                                 /outputs/artifacts
  ```

  * **MOUNT_PATH**: Location inside the pod where the NFS volume is mounted
  * **WORKFLOW_NAME**: The name of the Argo workflow
    * Each Argo workflow job has a unique name (enforced by APIServer)
    * So using WORKFLOW_NAME as root for all results associated with a particular job ensures there
      are no conflicts
  * **/src**: Any repositories that are checked out should be checked out here
     * Each repo should be checked out to the sub-directory **${REPO_ORG}/${REPO_NAME}**
  * **/outputs**: Any files that should be sync'd to GCS for Gubernator should be written here

### Step Image

* The Docker image used by the Argo steps should be a ksonnet parameter `stepImage`
* The Docker image should use an immutable image tag e.g `gcr.io/kubeflow-ci/test-worker:v20181017-bfeaaf5-dirty-4adcd0`

  * This ensures tests don't break if someone pushes a new test image

* The ksonnet parameter `stepImage` should be set in the `prow_config.yaml` file defining the E2E tests

  * This makes it easy to update all the workflows to use some new image.

* A common runtime is defined [here](https://github.com/kubeflow/testing/tree/master/images) and published to 
  [gcr.io/kubeflow-ci/test-worker](https://gcr.io/kubeflow-ci/test-worker)


### Checking out code

* The first step in the Argo workflow should checkout out the source repos to the NFS directory
* Use [checkout.sh](https://github.com/kubeflow/testing/blob/master/images/checkout.sh) to checkout the repos  
* checkout.sh environment variable `EXTRA_REPOS` allows checking out additional repositories in addition
  to the repository that triggered the pre/post submit test

  * This allows your test to use source code located in a different repository
  * You can specify whether to checkout the repository at HEAD or pin to a specific commit

* Most E2E tests will want to checkout kubeflow/testing in order to use various test utilities


### Building Docker Images

There are lots of different ways to build Docker images (e.g. GCB, Docker in Docker). Current recommendation
is

* Define a Makefile to provide a convenient way to invoke Docker builds
* Using Google Container Builder (GCB) to run builds in Kubeflow's CI system generally works better
  than alternatives (e.g. Docker in Docker, Kaniko)

  * Your Makefile can have alternative rules to support building locally via Docker for developers

* Use jsonnet if needed to define GCB workflows

  * Example [jsonnet file](https://github.com/kubeflow/examples/blob/master/code_search/docker/t2t/build.jsonnet)
    and associated [Makefile](https://github.com/kubeflow/examples/blob/master/code_search/Makefile)

* Makefile should expose variables for the following

  * Registry where image is pushed
  * TAG used for the images

* Argo workflow should define the image paths and tag so that subsequent steps can use the newly built images
