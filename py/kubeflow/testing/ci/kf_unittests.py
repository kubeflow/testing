""""Define the E2E workflows used to run unittests."""

from kubeflow.testing import argo_build_util
import logging
import os

# The name of the NFS volume claim to use for test files.
NFS_VOLUME_CLAIM = "nfs-external"
# The name to use for the volume to use to contain test data
DATA_VOLUME = "kubeflow-test-volume"

E2E_DAG_NAME = "e2e"
EXIT_DAG_NAME = "exit-handler"

TEMPLATE_LABEL = "kf_unittests"

class Builder: # pylint: disable=too-many-instance-attributes
  def __init__(self, name=None, namespace=None, bucket=None,
               test_target_name=None,
               **kwargs): # pylint: disable=unused-argument
    self.name = name
    self.namespace = namespace
    self.bucket = bucket
    self.test_target_name = test_target_name

    #****************************************************************************
    # Define directory locations
    #****************************************************************************
    # mount_path is the directory where the volume to store the test data
    # should be mounted.
    self.mount_path = "/mnt/" + "test-data-volume"
    # test_dir is the root directory for all data for a particular test run.
    self.test_dir = self.mount_path + "/" + self.name
    # output_dir is the directory to sync to GCS to contain the output for this
    # job.
    self.output_dir = self.test_dir + "/output"

    self.artifacts_dir = self.output_dir + "/artifacts/junit_{0}".format(name)

    # source directory where all repos should be checked out
    self.src_root_dir = self.test_dir + "/src"
    # The directory containing the kubeflow/kubeflow repo
    self.src_dir = self.src_root_dir + "/kubeflow/kubeflow"

    # Root of testing repo.
    self.testing_src_dir = os.path.join(self.src_root_dir, "kubeflow/testing")

    # Top level directories for python code
    self.kubeflow_py = self.src_dir

    # The directory within the kubeflow_testing submodule containing
    # py scripts to use.
    self.kubeflow_testing_py = self.src_root_dir + "/kubeflow/testing/py"

    self.go_path = self.test_dir

  def _build_workflow(self):
    """Create the scaffolding for the Argo workflow"""
    workflow = {
      "apiVersion": "argoproj.io/v1alpha1",
      "kind": "Workflow",
      "metadata": {
        "name": self.name,
        "namespace": self.namespace,
        "labels": argo_build_util.add_dicts([{
            "workflow": self.name,
            "workflow_template": TEMPLATE_LABEL,
          }, argo_build_util.get_prow_labels()]),
      },
      "spec": {
        "entrypoint": E2E_DAG_NAME,
        # Have argo garbage collect old workflows otherwise we overload the API
        # server.
        "ttlSecondsAfterFinished": 7 * 24 * 60 * 60,
        "volumes": [
          {
            "name": "gcp-credentials",
            "secret": {
              "secretName": "kubeflow-testing-credentials",
            },
          },
          {
            "name": DATA_VOLUME,
            "persistentVolumeClaim": {
              "claimName": NFS_VOLUME_CLAIM,
            },
          },
        ],
        "onExit": EXIT_DAG_NAME,
        "templates": [
          {
           "dag": {
                "tasks": [],
                },
           "name": E2E_DAG_NAME,
          },
          {
            "dag": {
              "tasks": [],
              },
              "name": EXIT_DAG_NAME,
            }
        ],
      },  # spec
    } # workflow

    return workflow

  def _build_task_template(self):
    """Return a template for all the tasks"""

    task_template = {'activeDeadlineSeconds': 3000,
     'container': {'command': [],
      'env': [
        {"name": "GOOGLE_APPLICATION_CREDENTIALS",
         "value": "/secret/gcp-credentials/key.json"}
       ],
      'image': 'gcr.io/kubeflow-ci/test-worker:latest',
      'imagePullPolicy': 'Always',
      'name': '',
      'resources': {'limits': {'cpu': '4', 'memory': '4Gi'},
       'requests': {'cpu': '1', 'memory': '1536Mi'}},
      'volumeMounts': [{'mountPath': '/mnt/test-data-volume',
        'name': 'kubeflow-test-volume'},
       {'mountPath': '/secret/gcp-credentials', 'name': 'gcp-credentials'}]},
     'metadata': {'labels': {
       'workflow_template': TEMPLATE_LABEL}},
     'outputs': {}}

    # Define common environment variables to be added to all steps
    common_env = [
      {'name': 'PYTHONPATH',
       'value': ":".join([self.kubeflow_py, self.kubeflow_testing_py])},
      {'name': 'GOPATH',
        'value': self.go_path},
      {'name': 'KUBECONFIG',
       'value': os.path.join(self.test_dir, 'kfctl_test/.kube/kubeconfig')},
    ]

    task_template["container"]["env"].extend(common_env)

    if self.test_target_name:
      task_template["container"]["env"].append({
        'name': 'TEST_TARGET_NAME',
        'value': self.test_target_name,
      })

    task_template = argo_build_util.add_prow_env(task_template)

    return task_template

  def build(self):
    workflow = self._build_workflow()
    task_template = self._build_task_template()

    #**************************************************************************
    # Checkout

    # create the checkout step
    main_repo = argo_build_util.get_repo_from_prow_env()
    if not main_repo:
      logging.info("Prow environment variables for repo not set")
      main_repo = "kubeflow/testing@HEAD"
    logging.info("Main repository: %s", main_repo)
    repos = [main_repo]

    checkout = argo_build_util.deep_copy(task_template)

    checkout["name"] = "checkout"
    checkout["container"]["command"] = ["/usr/local/bin/checkout_repos.sh",
                                        "--repos=" + ",".join(repos),
                                        "--src_dir=" + self.src_root_dir]

    argo_build_util.add_task_to_dag(workflow, E2E_DAG_NAME, checkout, [])

    #**************************************************************************
    # Make dir
    # pytest was failing trying to call makedirs. My suspicion is its
    # because the two steps ended up trying to create the directory at the
    # same time and classing. So we create a separate step to do it.
    mkdir_step = argo_build_util.deep_copy(task_template)

    mkdir_step["name"] = "make-artifacts-dir"
    mkdir_step["container"]["command"] = ["mkdir",
                                          "-p",
                                          self.artifacts_dir]


    argo_build_util.add_task_to_dag(workflow, E2E_DAG_NAME, py_tests,
                                    [checkout["name"]])

    #**************************************************************************
    # Run python unittests
    py_tests = argo_build_util.deep_copy(task_template)

    py_tests["name"] = "py-test"
    py_tests["container"]["command"] = ["python",
                                        "-m",
                                        "kubeflow.testing.test_py_checks",
                                        "--artifacts_dir=" + self.artifacts_dir,
                                        # TODO(jlewi): Should we be searching
                                        # the entire py/kubeflo/testing tree?
                                        "--src_dir=" + self.kubeflow_testing_py
                                        + "kubeflow/tests"]


    argo_build_util.add_task_to_dag(workflow, E2E_DAG_NAME, py_tests,
                                    [mkdir_step["name"]])


    #***************************************************************************
    # py lint
    #***************************************************************************
    py_lint = argo_build_util.deep_copy(task_template)

    py_lint["name"] = "py-lint"
    py_lint["container"]["command"] = ["pytest",
                                       "test_py_lint.py",
                                       # I think -s mean stdout/stderr will
                                       # print out to aid in debugging.
                                       # Failures still appear to be captured
                                       # and stored in the junit file.
                                       "-s",
                                       "--src_dir=" + self.kubeflow_testing_py,
                                       "--rcfile=" + os.path.join(
                                         self.testing_src_dir, ".pylintrc"),
                                       # Test timeout in seconds.
                                       "--timeout=500",
                                       "--junitxml=" + self.artifacts_dir +
                                       "/junit_py-lint.xml"]

    py_lint_step = argo_build_util.add_task_to_dag(workflow, E2E_DAG_NAME,
                                                   py_lint,
                                                   [mkdir_step["name"])

    py_lint_step["container"]["workingDir"] = os.path.join(
      self.testing_src_dir, "py/kubeflow/testing")

    #*****************************************************************************
    # create_pr_symlink
    #****************************************************************************
    # TODO(jlewi): run_e2e_workflow.py should probably create the PR symlink
    symlink = argo_build_util.deep_copy(task_template)

    symlink["name"] = "create-pr-symlink"
    symlink["container"]["command"] = ["python",
                                       "-m",
                                       "kubeflow.testing.prow_artifacts",
                                       "--artifacts_dir=" + self.output_dir,
                                       "create_pr_symlink",
                                       ]

    if self.bucket:
      symlink["container"]["command"].append("--bucket=" + self.bucket)

    argo_build_util.add_task_to_dag(workflow, E2E_DAG_NAME, symlink,
                                    [checkout["name"]])

    #*****************************************************************************
    # Exit handler workflow
    #*****************************************************************************
    copy_artifacts = argo_build_util.deep_copy(task_template)

    copy_artifacts["name"] = "copy-artifacts"
    copy_artifacts["container"]["command"] = ["python",
                                              "-m",
                                              "kubeflow.testing.prow_artifacts",
                                              "--artifacts_dir=" +
                                              self.output_dir,
                                              "copy_artifacts"]

    if self.bucket:
      copy_artifacts["container"]["command"].append("--bucket=" + self.bucket)


    argo_build_util.add_task_to_dag(workflow, EXIT_DAG_NAME, copy_artifacts, [])


    # Set the labels on all templates
    workflow = argo_build_util.set_task_template_labels(workflow)

    return workflow

def create_workflow(name=None, namespace=None, bucket=None, **kwargs): # pylint: disable=too-many-statements
  """Create workflow returns an Argo workflow to test kfctl upgrades.

  Args:
    name: Name to give to the workflow. This can also be used to name things
     associated with the workflow.
  """

  builder = Builder(name=name, namespace=namespace, bucket=bucket, **kwargs)

  return builder.build()
