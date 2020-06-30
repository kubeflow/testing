<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Tekton for Kubeflow](#tekton-for-kubeflow)
  - [Adding Tekton Tests To Your Repo](#adding-tekton-tests-to-your-repo)
  - [Reporting test results to Prow](#reporting-test-results-to-prow)
  - [Kubeflow's Catalog of Reusable Tasks and Pipelines](#kubeflows-catalog-of-reusable-tasks-and-pipelines)
  - [Running on your own Tekton cluster](#running-on-your-own-tekton-cluster)
  - [Tekton Cluster](#tekton-cluster)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Tekton for Kubeflow

We have started using Tekton to for CI/CD with Kubeflow. 

## Adding Tekton Tests To Your Repo

To write a test using Tekton you first create a YAML file containing a Tekton 
[PipelineRun](https://github.com/tektoncd/pipeline/blob/master/docs/pipelineruns.md) inside your directory.

The PipelineRun can either inline the [PipelineSpec](https://github.com/tektoncd/pipeline/blob/master/docs/pipelineruns.md#specifying-the-target-pipeline) or it can refer to an existing Kubeflow Pipeline defined
in the KF Tekton cluster. 

Likewise your Pipeline can either inline Tekton Tasks or refer to inline Tekton tasks already in the cluster.

Your Pipeline should contain at least one [PipelineResource](https://github.com/tektoncd/pipeline/blob/master/docs/resources.md)
specifying the Git repo to be tested. In presubmits and postsubmits [run_e2e_workflow.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/run_e2e_workflow.py) will replace the revision for the repo being tested with the commit being tested.

To trigger the tests add an entry to your prow_config.yaml to trigger the test

```
      tekton_run: kubeflow/testing/tekton/runs/nb-test-run.yaml
      tekton_params:
        - name: testing-cluster-pattern
          value: kf-v1-(?!n\d\d)   
      name: tekton-v1
      include_dirs:
        - py/*
```

| Name | Description |
| --- | --- |
|name| Name for your pipeline |
|tekton_run| Path the YAML file defining the PipelineRun |
|tekton_params | specify values for parameters defined by your pipeline |
|include_dirs | (Optional) only trigger when the PR modifies matching files |


Optionally you can specify a second PipelineRun to be run to teardown any resource you might have setup.

```
      tekton_run: kubeflow/testing/tekton/testing/nb-test-run.yaml
      tekton_params:
        - name: testing-cluster-pattern
          value: 'kf-v1-(?!n\d\d)'   
      name: tekton-v1
      include_dirs:
        - py/*     
      tekton_teardown: kubeflow/testing/tekton/testing/dummy-teardown-run.yaml
      tekton_teardown_params:
        - name: utter
          value: bar
```


This is a work around for the fact that Tekton currently doesn't have a mechanism for always running some tasks 
even if the earlier tasks fail (see [tektoncd/pipeline#1684](https://github.com/tektoncd/pipeline/issues/1684))

Optionally you can specify a list of job types ("presubmit", "postsubmit", or "periodic") on which to trigger.

```
      tekton_run: kubeflow/testing/tekton/testing/nb-test-run.yaml
      tekton_params:
        - name: testing-cluster-pattern
          value: 'kf-v1-(?!n\d\d)'   
      name: tekton-v1
      include_dirs:
        - py/*     
      tekton_teardown: kubeflow/testing/tekton/testing/dummy-teardown-run.yaml
      tekton_teardown_params:
        - name: utter
          value: bar
      job_types:
        - postsubmit
```

## Reporting test results to Prow

To report test results to prow you need to upload a junit XML file to the appropriate GCS location.

To create a Tekton task that reports results to prow your task needs to do the following

* Emit a junit file
* Copy the junit file to the appropriate location

Typically you do this by adding a step to your tekton task that uses [tekton_client.py](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/tekton_client.py) to upload the results and any other artifacts.

**Important** Once a Tekton step errors out no subsequent tasks or steps are run. This means you want to avoid having your steps
exit with non-zero exit code if you depend on subsequent steps to upload the results. 
Tekton is currently working on a better strategy for failures (see [tektoncd/pipeline#1684](https://github.com/tektoncd/pipeline/issues/1684)).


## Kubeflow's Catalog of Reusable Tasks and Pipelines

Kubeflow is building out a reusable catalog of tasks and pipelines; e.g. for running lint and unittests.

The resuable catalog is defined in [tekton/templates](https://github.com/kubeflow/testing/tree/master/tekton/templates). 
Note these are unhydrated manifests. 

Hydrated manifests are stored in [acm-repos/kf-ci-v1](https://github.com/kubeflow/testing/tree/master/acm-repos/kf-ci-v1).
ACM is used to automatically sync that directory to the cluster.

To update the hydrated manifests

```
make hydrate
```

## Debugging 

### TaskRun Logs

If the logs aren't available in the Tekton UI you can fetch them with a query like the one below.

```
resource.type="k8s_container"
resource.labels.cluster_name="kf-ci-v1"
labels."k8s-pod/tekton_dev/taskRun" = "mnist-wc6fq-run-notebook-d9q7w"
resource.labels.container_name = "step-copy-artifacts"
```

## Running on your own Tekton cluster

You should be able to run the KF Tekton pipelines on your own Tekton cluster provided you install
any Kubeflow Pipelines/Tasks that the test is referring to on your cluster.

## Tekton Cluster

Tekton is currently installed in the following cluster.

* **project**: kubeflow-ci
* **cluster**: kf-ci-v1
* **zone**: us-east1-d
* **namespace**: kf-ci
  * The namespace where Tekton jos run.

The Tekton dashboard is accessbile at [https://kf-ci-v1.endpoints.kubeflow-ci.cloud.goog/tekton/#/](https://kf-ci-v1.endpoints.kubeflow-ci.cloud.goog/tekton/#/)

## What's Next

* [tekton/README.md](../tekton/README.md) for more info on writing pipelines
