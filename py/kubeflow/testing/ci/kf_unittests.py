""""Define the E2E workflows used to run unittests."""

from kubeflow.testing import argo_build_util
import os

# The name of the NFS volume claim to use for test files.
NFS_VOLUME_CLAIM = "nfs-external"
# The name to use for the volume to use to contain test data
DATA_VOLUME = "kubeflow-test-volume"

EXIT_DAG_NAME = "exit-handler"

WORKFLOW_TEMPLATE = {
  "apiVersion": "argoproj.io/v1alpha1",
  "kind": "Workflow",
  "metadata": {
  },
  "spec": {
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
    "templates": [],
  },  # spec
} # workflow

TEMPLATE_LABEL = "kf_unittests"

DEFAULT_TEMPLATE = {'activeDeadlineSeconds': 3000,
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

def create_workflow(name=None, namespace=None, bucket="kubeflow-ci_temp"): # pylint: disable=too-many-statements
  """Create workflow returns an Argo workflow to test kfctl upgrades.

  Args:
    name: Name to give to the workflow. This can also be used to name things
     associated with the workflow.
  """
  workflow = WORKFLOW_TEMPLATE
  workflow["metadata"]["name"] = name
  workflow["metadata"]["namespace"] = namespace

  workflow["metadata"]["labels"] = {
    "workflow": name,
    "workflow_template": TEMPLATE_LABEL,
  }

  e2e_dag_name = "e2e"

  workflow["spec"]["entrypoint"] = e2e_dag_name

  # Define the E2E dag
  workflow["spec"]["templates"].extend([
    {
      "dag": {
        "tasks": [],
      },
      "name": e2e_dag_name,
    },
    {
      "dag": {
        "tasks": [],
      },
      "name": EXIT_DAG_NAME,
    }
  ])

  prow_dict = argo_build_util.get_prow_labels()

  for k, v in prow_dict.items():
    workflow["metadata"]["labels"][k] = v

  #****************************************************************************
  # Define directory locations
  #****************************************************************************
  # mount_path is the directory where the volume to store the test data
  # should be mounted.
  mount_path = "/mnt/" + "test-data-volume"
  # test_dir is the root directory for all data for a particular test run.
  test_dir = mount_path + "/" + name
  # output_dir is the directory to sync to GCS to contain the output for this
  # job.
  output_dir = test_dir + "/output"
  artifacts_dir = output_dir + "/artifacts"

  # source directory where all repos should be checked out
  src_root_dir = test_dir + "/src"
  # The directory containing the kubeflow/kubeflow repo
  src_dir = src_root_dir + "/kubeflow/kubeflow"

  # Top level directories for python code
  kubeflow_py = src_dir

  # The directory within the kubeflow_testing submodule containing
  # py scripts to use.
  kubeflow_testing_py = src_root_dir + "/kubeflow/testing/py"

  go_path = test_dir

  # Define common environment variables to be added to all steps
  common_env = [
    {'name': 'PYTHONPATH',
     'value': ":".join([kubeflow_py, kubeflow_testing_py])},
    {'name': 'GOPATH',
      'value': go_path},
    {'name': 'KUBECONFIG',
     'value': os.path.join(test_dir, 'kfctl_test/.kube/kubeconfig')},
  ]

  DEFAULT_TEMPLATE["container"]["env"].extend(common_env)

  # create the checkout step
  job_type = os.getenv("JOB_TYPE", "").lower()
  if  job_type == "presubmit":
    repos = "kubeflow/testing@{0}:{1}".format(
      os.getenv("PULL_PULL_SHA", "HEAD"), os.getenv("PULL_NUMBER"))
  elif job_type == "postsubmit":
    repos = "kubeflow/testing@{0}".format(os.getenv("PULL_BASE_SHA"))
  else:
    branch = os.getenv("BRANCH_NAME", "HEAD")
    repos = "kubeflow/testing@{0}".format(branch)

  #**************************************************************************
  # Checkout
  checkout = argo_build_util.deep_copy(DEFAULT_TEMPLATE)
  checkout = argo_build_util.add_prow_env(checkout)

  checkout["name"] = "checkout"
  checkout["container"]["command"] = ["/usr/local/bin/checkout_repos.sh",
                                      "--repos=" + repos,
                                      "--src_dir="+src_root_dir]
  checkout["metadata"]["labels"] = {
    'step_name': 'checkout',
    "workflow": name,
  }
  checkout["metadata"]["labels"].update(prow_dict)

  argo_build_util.add_task_to_dag(workflow, e2e_dag_name, checkout, [])

  #**************************************************************************
  # Run python unittests
  py_tests = argo_build_util.deep_copy(DEFAULT_TEMPLATE)
  py_tests = argo_build_util.add_prow_env(py_tests)

  py_tests["name"] = "py-test"
  py_tests["container"]["command"] = ["python",
                                      "-m",
                                      "kubeflow.testing.test_py_checks",
                                      "--artifacts_dir=" + artifacts_dir,
                                      # TODO(jlewi): Should we be searching
                                      # the entire py/kubeflo/testing tree?
                                      "--src_dir=" + kubeflow_testing_py + "kubeflow/tests"]

  py_tests["metadata"]["labels"] = {
    'step_name': 'py-test',
    "workflow": name,
  }
  py_tests["metadata"]["labels"].update(prow_dict)

  argo_build_util.add_task_to_dag(workflow, e2e_dag_name, py_tests, [checkout["name"]])


  #*****************************************************************************
  # py lint
  #****************************************************************************
  py_lint = argo_build_util.deep_copy(DEFAULT_TEMPLATE)
  py_lint = argo_build_util.add_prow_env(py_lint)

  py_lint["name"] = "py-lint"
  py_lint["container"]["command"] = ["python",
                                     "-m",
                                     "kubeflow.testing.test_py_lint",
                                     "--artifacts_dir=" + artifacts_dir,
                                     "--src_dir=" + kubeflow_testing_py,
                                     ]
  py_lint["metadata"]["labels"] = {
    'step_name': py_lint["name"],
    "workflow": name,
  }
  py_lint["metadata"]["labels"].update(prow_dict)

  argo_build_util.add_task_to_dag(workflow, e2e_dag_name, py_lint, [checkout["name"]])

  #*****************************************************************************
  # create_pr_symlink
  #****************************************************************************
  # TODO(jlewi): run_e2e_workflow.py should probably create the PR symlink
  symlink = argo_build_util.deep_copy(DEFAULT_TEMPLATE)
  symlink = argo_build_util.add_prow_env(symlink)

  symlink["name"] = "create-pr-symlink"
  symlink["container"]["command"] = ["python",
                                     "-m",
                                     "kubeflow.testing.prow_artifacts",
                                     "--artifacts_dir=" + output_dir,
                                     "create_pr_symlink",
                                     "--bucket=" + bucket,
                                     ]
  symlink["metadata"]["labels"] = {
    'step_name': symlink["name"],
    "workflow": name,
  }
  symlink["metadata"]["labels"].update(prow_dict)

  argo_build_util.add_task_to_dag(workflow, e2e_dag_name, symlink, [checkout["name"]])

  #*****************************************************************************
  # Exit handler workflow
  #*****************************************************************************
  copy_artifacts = argo_build_util.deep_copy(DEFAULT_TEMPLATE)
  copy_artifacts = argo_build_util.add_prow_env(copy_artifacts)

  copy_artifacts["name"] = "copy-artifacts"
  copy_artifacts["container"]["command"] = ["python",
                                            "-m",
                                            "kubeflow.testing.prow_artifacts",
                                            "--artifacts_dir=" + output_dir,
                                            "copy_artifacts",
                                            "--bucket=" + bucket,
                                            "--suffix=fakesuffix",]
  copy_artifacts["metadata"]["labels"] = {
    'step_name': copy_artifacts["name"],
    "workflow": name,
  }
  copy_artifacts["metadata"]["labels"].update(prow_dict)

  argo_build_util.add_task_to_dag(workflow, EXIT_DAG_NAME, copy_artifacts, [])

  return workflow
