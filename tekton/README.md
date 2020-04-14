# Tekton Based Tests

This directory contains Kubeflow tests templates in Tekton.

We aim to provide self-contained tests settings by using Tekton.

A Tekton test is involved at 2 parts:

  * A `Task`, which acts as a template to run tests.  For example, a notebook testing `Task` takes as input path to a Jupyter notebook and runs it as test.
  * A `PipelineRun`, which brings up Tekton pipelines to run the tests.

## How to write a Task

A task should be self-contained:

  * Prepare testing environment. For example, getting proper identifications.
  * Runs tests in steps.
  * Collect test artifacts such as JUNIT XML files.
  * Upload to GCS location.

Things to note:
  * Any failure would stop the task from running subsequent steps. Therefore users need to make sure all the steps don't error out unless it is intentional.
  * In the kubeflow/testing repo, we have handy function in tekton\_client.py for you to upload your artifacts.

## How to write a PipelineRun

A `PipelineRun` defines all the tasks you'd like to run. A well-defined `PipelineRun` will be a Tekton pipeline that could be easily run either on Prow or manually by user.

A `PipelineRun` runs a series of tasks:

  * Sets up shared testing targets, such as a shared KF Cluster.
  * Runs all the tests defined as tasks.

Things to note:
  * Similarly if a given task is failed, all the depending tasks in the graph will not be run.
  * Each task runs in separate pod, so the state is not shared. Make sure each task is self-contained.
  * To make the PipelineRun portable, your PipelineRun should be able to run manually by assigning values to params.

### IMPORTANT: Params we inject when running on Prow

When the PipelineRun runs on Prow, our script injects the following params to each PipelineRun, including teardown process:
  * test-target-name: This is normally used as classname in JUNIT.
  * artifacts-gcs: This points to the GCS location directories of artifacts will be uploaded to.
  * junit-path: Relative path to the GCS artifacts will be uploaded to. Final GCS blob will be <artifacts-gcs>/<junit-path>

### IMPORTANT: Repository under test needs to be declared

During the test firing off, we will loop through resources in PipelineRun and update the git revision on the fly. Users need to declare the repository under test or an error will be thrown.

### Optional: Teardown PipelineRun

A teardown PipelineRun has to be separated from the usual PipelineRun that runs tests. The reason is because teardown process should be invoked whether or not any of the tasks succeeds. For instance, a testing KF cluster has to be brought down regardless of the state of tests.

## Fields in prow\_config.yaml

We introduce the following fields for users to define new Tekton pipeline to run on Prow.

```yaml
- name: <test-name>
  # Here we define a PipelineRun to run.
  tekton_run: kubeflow/<repo-name>/path/to/your-pipelinerun.yaml
  tekton_params:
  - name: your-param
    value: param-value
  # Optional we could define a teardown PipelineRun.
  tekton_teardown: kubeflow/<repo-name>/path/to/your-teardown-pipelinerun.yaml
  tekton_teardown_params:
  - name: your-param
    value: param-value
```

**tekton_run**: Points to the PipelineRun file the test runs.
**tekton_params**: Optionally you could assign values to the PipelineRuns parameters. This is helpful when you reuse a PipelineRun.
**tekton_teardown**: Points to the PipelineRun file the teardown process runs.
**tekton_teardown_params**: Parameters assigned to teardown process.
