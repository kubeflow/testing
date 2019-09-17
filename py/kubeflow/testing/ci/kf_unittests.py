""""Define the E2E workflows used to run unittests."""

from kubeflow.testing import argo_client
import fire
import os
import yaml

# The name of the NFS volume claim to use for test files.
NFS_VOLUME_CLAIM  = "nfs-external"
# The name to use for the volume to use to contain test data
DATA_VOLUME = "kubeflow-test-volume"

WORKFLOW_TEMPLATE = {
  "apiVersion": "argoproj.io/v1alpha1",
  "kind": "Workflow",
  "metadata": {
  },
  "spec": {
    #Have argo garbage collect old workflows otherwise we overload the API server.
    "ttlSecondsAfterFinished": 7 * 24 * 60 * 60,
    "volumes": [
      # TODO(jlewi): We should be able to delete the github-token since
      # we aren't using ksonnet anymore
      #{
      #  "name": "github-token",
      #  "secret": {
      #    "secretName": "github-token",
      #  },
      #},
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
    # onExit specifies the template that should always run when the workflow completes.
    #"onExit": "exit-handler",
    "templates": [],
  },  # spec
} # workflow


TEMPLATE_LABEL = "kf_unittests"

DEFAULT_TEMPLATE = {'activeDeadlineSeconds': 3000,
 'container': {'command': [],
  'env': [
   # TODO(jlewi): We shouldn't need a GITHUB_TOKEN since we aren't using
   # ksonnet anymore.
   #{'name': 'GITHUB_TOKEN',
   # 'valueFrom': {'secretKeyRef': {'key': 'github_token',
   #   'name': 'github-token'}}},
   ],
  'image': 'gcr.io/kubeflow-ci/test-worker:latest',
  'imagePullPolicy': 'Always',
  'name': '',
  'resources': {'limits': {'cpu': '4', 'memory': '4Gi'},
   'requests': {'cpu': '1', 'memory': '1536Mi'}},
  'volumeMounts': [{'mountPath': '/mnt/test-data-volume',
    'name': 'kubeflow-test-volume'},
   # TODO(jlewi): Shouldn't need a GITHUB_TOKEN anymore since we aren't
   # using ksonnet.
   # {'mountPath': '/secret/github-token', 'name': 'github-token'},
   {'mountPath': '/secret/gcp-credentials', 'name': 'gcp-credentials'}]},
 'metadata': {'labels': {
   'workflow_template': TEMPLATE_LABEL}},
 'outputs': {}}

#The name for the workspace to run the steps in
# local stepsNamespace = "kubeflow";

# runPath = srcDir + "/testing/workflows/run.sh";
# kfCtlPath = srcDir + "/bootstrap/bin/kfctl";
# kubeConfig = test_dir + "/kfctl_test/.kube/kubeconfig";

# Directory containing the app. This is the directory
# we execute kfctl commands from
#APP_DIR = TEST_DIR + "/" + appName;

#IMAGE = "gcr.io/kubeflow-ci/test-worker:latest";
#TESTING_IMAGE = "gcr.io/kubeflow-ci/kubeflow-testing";

def get_prow_dict():
  # see https://github.com/kubernetes/test-infra/blob/70015225876afea36de3ce98f36fe1592e8c2e53/prow/jobs.md
  prow_vars = ["JOB_NAME", "JOB_TYPE", "JOB_SPEC", "BUILD_ID", "PROW_JOB_ID",
               "REPO_OWNER", "REPO_NAME", "PULL_BASE_REF", "PULL_REFS",
               "PULL_NUMBER", "PULL_PULL_SHA"]

  d = {}
  for v in prow_vars:
    if not os.getenv(v):
      continue

    d[v] = os.getenv(v)

  return d

def get_prow_labels():
  """Return a dictionary of prow labels suitable for use as labels"""
  # see https://github.com/kubernetes/test-infra/blob/70015225876afea36de3ce98f36fe1592e8c2e53/prow/jobs.md
  prow_vars = ["JOB_NAME", "JOB_TYPE", "BUILD_ID", "PROW_JOB_ID",
               "REPO_OWNER", "REPO_NAME", "PULL_NUMBER"]

  d = {}
  for v in prow_vars:
    if not os.getenv(v):
      continue

    d[v] = os.getenv(v)

  return d

def add_prow_env(spec):
  """Copy any prow environment variables to the step.

  Args:
    spec: Argo template spec

  Returns:
    spec: Updated spec
  """

  if not spec.get("container").get("env"):
    spec["container"]["env"] = []

  prow_dict = get_prow_dict()
  for k, v in prow_dict.items():
    spec["container"]["env"].append({"name": k,
                                     "value": v})

  for k, v in get_prow_labels():
    spec["metadata"]["labels"][k] = v
  return spec

def deep_copy(d):
  """Perform a deep copy of the supplied object"""
  s = yaml.dump(d)
  return yaml.load(s)

def add_task_to_dag(workflow, dag_name, task, dependencies):
  """Add a task to the specified workflow.

  Args:
    workflow: The workflow spec
    dag_name: The name of the dag to add the step to
    task: The task template
    dependencies: A list of dependencies
  """

  dag = None
  for t in workflow["spec"]["templates"]:
    if "dag" not in t:
      continue
    if t["name"] == dag_name:
      dag = t

  if not dag:
    raise ValueError("No dag named {0} found".format(dag_name))

  if not dag["dag"].get("tasks"):
    dag["dag"]["tasks"] = []

  dag["dag"]["tasks"].append(
    {
      "name": task["name"],
      "template": task["name"],
    }
  )

  workflow["spec"]["templates"].append(task)

def create_workflow(name=None, namespace=None, *kwargs):
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
  # TODO(jlewi): Need to add the on-exit dag.
  workflow["spec"]["templates"].append(
    {
      "dag": {
        "tasks": [],
      },
      "name": e2e_dag_name,
    }
  )

  prow_dict = get_prow_labels()

  for k, v in prow_dict.items():
    workflow["metadata"]["labels"][k] = v

  #****************************************************************************
  # Define directory locations
  #****************************************************************************
  #The name for the workspace to run the steps in
  # local stepsNamespace = "kubeflow";

  # mount_path is the directory where the volume to store the test data
  # should be mounted.
  mount_path = "/mnt/" + "test-data-volume"
  # test_dir is the root directory for all data for a particular test run.
  test_dir = mount_path + "/" + name
  # output_dir is the directory to sync to GCS to contain the output for this job.
  output_dir = test_dir + "/output";
  artifacts_dir = output_dir + "/artifacts";
  # source directory where all repos should be checked out
  src_root_dir = test_dir + "/src";
  # The directory containing the kubeflow/kubeflow repo
  src_dir = src_root_dir + "/kubeflow/kubeflow";


  # Top level directories for python code
  kubeflow_py = src_dir

  # The directory within the kubeflow_testing submodule containing
  # py scripts to use.
  kubeflow_testing_py = src_root_dir + "/kubeflow/testing/py"

  go_path = test_dir

  # runPath = srcDir + "/testing/workflows/run.sh";
  # kfCtlPath = srcDir + "/bootstrap/bin/kfctl";
  # kubeConfig = test_dir + "/kfctl_test/.kube/kubeconfig";
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
    repos = "kubeflow/testing@{0}:{1}".format(os.getenv("PULL_PULL_SHA"), os.getenv("PULL_NUMBER"))
  elif job_type == "postsubmit":
    repos = "kubeflow/testing@{0}".format(os.getenv("PULL_BASE_SHA"))
  else:
    branch = os.getenv("BRANCH_NAME", "HEAD")
    repos = "kubeflow/testing@{0}".format(branch)

  checkout = deep_copy(DEFAULT_TEMPLATE)
  checkout = add_prow_env(checkout)

  checkout["name"] = "checkout"
  checkout["container"]["command"] = ["/usr/local/bin/checkout_repos.sh",
                                      "--repos=" + repos,
                                      "--src_dir="+src_root_dir]
  checkout["metadata"]["labels"] = {
    'step_name': 'checkout',
    "workflow": name,
  }
  checkout["metadata"]["labels"].update(prow_dict)

  add_task_to_dag(workflow, e2e_dag_name, checkout, [])

  return workflow


