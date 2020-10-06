"""Run the E2E workflow.

This script submits Argo workflows to run the E2E tests and waits for
them to finish. It is intended to be invoked by prow jobs.

It requires the workflow to be expressed as a ksonnet app or a Python function.

The script can take a config file via --config_file.
The --config_file is expected to be a YAML file as follows:

workflows:
  - name: workflow-test
    job_types:
      presubmit
    py_func: my_test_package.my_test_module.my_test_workflow
    kwargs:
        arg1: argument

  - name: e2e-test
    app_dir: tensorflow/k8s/test/workflows
    component: workflows
    job_types:
      presubmit
    include_dirs:
      tensorflow/*

python_paths:
 - ${REPO_OWNER}/${REPO_NAME}/some/path

app_dir is expected to be in the form ofx
{REPO_OWNER}/{REPO_NAME}/path/to/ksonnet/app

python paths is a list of paths to add to the python path; typically
you will list the path to the directory containing the top level package
for the py_func to generate the test for your workflow.

component is the name of the ksonnet component corresponding
to the workflow to launch.

job_types (optional) is an array of strings representing the job types (presubmit/postsubmit)
that should run this workflow.

include_dirs (optional) is an array of strings that specify which directories, if modified,
should run this workflow.

py_func is the Python method to invoke Argo workflows

kwargs is an array of arguments passed to the Python method

The script expects that the directories
{repos_dir}/{app_dir} exists. Where repos_dir is provided
as a command line argument.
"""

import argparse
import datetime
import fnmatch
import importlib
import logging
import os
import tempfile
import six
from kubernetes import client as k8s_client
from kubeflow.testing import argo_client
from kubeflow.testing import ks_util
from kubeflow.testing import prow_artifacts
from kubeflow.testing import tekton_client
from kubeflow.testing import util
import uuid
import subprocess
import sys
import traceback
import yaml

if os.getenv("CLOUD_PROVIDER") == "aws":
  from kubeflow.testing.cloudprovider.aws import prow_artifacts as aws_prow_artifacts
  from kubeflow.testing.cloudprovider.aws import util as aws_util

# The name of the command line argument for workflows for the var
# to contain the test target name.
# The goal is to be able to use target name grouping in test grid
# to group related tests
# https://github.com/kubernetes/test-infra/tree/master/testgrid#grouping-tests
TEST_TARGET_ARG_NAME = "test_target_name"

# Tekton pipelines run on different cluster.
TEKTON_CLUSTER_NAME = "kf-ci-v1"
TEKTON_CLUSTER_ZONE = "us-east1-d"

if six.PY2:
  FileNotFoundError = IOError


# The namespace to launch the Argo workflow in.
def get_namespace(args):
  if args.namespace:
    return args.namespace

  if args.release:
    return "kubeflow-releasing"
  return "kubeflow-test-infra"

# imports py_func
def py_func_import(py_func, kwargs):
  """Imports and executes the function py_func."""
  path, create_function = py_func.rsplit('.', 1)
  logging.info("Importing path %s", path)
  mod = importlib.import_module(path)
  met = getattr(mod, create_function)
  return met(**kwargs)

class WorkflowComponent(object): # pylint: disable=too-many-instance-attributes,disable=useless-object-inheritance
  """Datastructure to represent a component to submit a workflow."""
  def __init__(self, root_dir, data):
    self.name = data.get("name")
    self.job_types = data.get("job_types", [])
    self.include_dirs = data.get("include_dirs", [])
    self.app_dir = os.path.join(root_dir, data.get("app_dir")) if data.get("app_dir") else ""
    self.tekton_run = os.path.join(root_dir, data.get("tekton_run")) if data.get("tekton_run") else ""
    self.tekton_params = data.get("tekton_params", [])
    self.tekton_teardown = os.path.join(root_dir, data.get("tekton_teardown")) if data.get("tekton_teardown") else ""
    self.tekton_teardown_params = data.get("tekton_teardown_params", [])
    self.component = data.get("component")
    self.params = data.get("params", {})
    self.py_func = data.get("py_func")
    self.kwargs = data.get("kwargs", {})

def _get_src_dir():
  return os.path.abspath(os.path.join(__file__, "..",))

def create_started_file(bucket, ui_urls):
  """Create the started file in gcs for gubernator."""
  contents = prow_artifacts.create_started(ui_urls)

  target = os.path.join(prow_artifacts.get_gcs_dir(bucket), "started.json")
  util.upload_to_gcs(contents, target)


def create_started_file_s3(bucket, ui_urls):
  """Create the started file in S3 for gubernator."""
  contents = aws_prow_artifacts.create_started(ui_urls)

  target = os.path.join(aws_prow_artifacts.get_s3_dir(bucket), "started.json")
  aws_util.upload_to_s3(contents, target, "started.json")


def parse_config_file(config_file, root_dir):
  with open(config_file) as hf:
    config = yaml.load(hf)

  components = []
  for i in config["workflows"]:
    components.append(WorkflowComponent(root_dir, i))
  return config, components

def generate_env_from_head(args):
  commit = util.run(["git", "rev-parse", "HEAD"], cwd=os.path.join(
    args.repos_dir, os.getenv("REPO_OWNER"), os.getenv("REPO_NAME")))
  pull_base_sha = commit[0:8]
  date_str = datetime.datetime.now().strftime("%Y%m%d")
  build_number = uuid.uuid4().hex[0:4]
  version_tag = "v{0}-{1}".format(date_str, pull_base_sha)
  env_var = {
    "PULL_BASE_SHA": pull_base_sha,
    "BUILD_NUMBER": build_number,
    "VERSION_TAG": version_tag,
  }

  for k in env_var:
    if os.getenv(k):
      continue
    os.environ[k] = env_var.get(k)

def run(args, file_handler): # pylint: disable=too-many-statements,too-many-branches
  # Check https://github.com/kubernetes/test-infra/blob/master/prow/jobs.md
  # for a description of the injected environment variables.
  job_type = os.getenv("JOB_TYPE")
  repo_owner = os.getenv("REPO_OWNER")
  repo_name = os.getenv("REPO_NAME")
  base_branch_name = os.getenv("PULL_BASE_REF")
  pull_base_sha = os.getenv("PULL_BASE_SHA")

  # For presubmit/postsubmit jobs, find the list of files changed by the PR.
  diff_command = []
  if job_type == "presubmit":
    # We need to get a common ancestor for the PR and the base branch
    cloned_repo_dir = os.path.join(args.repos_dir, repo_owner, repo_name)

    _ = util.run(["git", "fetch", "origin", base_branch_name + ":refs/remotes/origin/" +
                  base_branch_name], cwd=cloned_repo_dir)

    diff_command = ["git", "diff", "--name-only"]
    diff_branch = "remotes/origin/{}".format(base_branch_name)
    try:
      common_ancestor = util.run(["git", "merge-base", "HEAD", diff_branch],
                                 cwd=cloned_repo_dir)
      diff_command.append(common_ancestor)
    except subprocess.CalledProcessError as e:
      logging.warning("git merge-base failed; see "
                      "https://github.com/kubeflow/kubeflow/issues/3523. Diff "
                      "will be computed against the current master and "
                      "therefore files not changed in the PR might be "
                      "considered when determining which tests to trigger")
      diff_command.append(diff_branch)

  elif job_type == "postsubmit":
    # See: https://git-scm.com/docs/git-diff
    # This syntax compares the commit before pull_base_sha with the commit
    # at pull_base_sha
    diff_command = ["git", "diff", "--name-only", pull_base_sha + "^", pull_base_sha]

  changed_files = []
  if job_type in ("presubmit", "postsubmit"):
    changed_files = util.run(diff_command,
      cwd=os.path.join(args.repos_dir, repo_owner, repo_name)).splitlines()

  for f in changed_files:
    logging.info("File %s is modified.", f)

  if args.release:
    generate_env_from_head(args)
  workflows = []
  config = {}
  if args.config_file:
    config, new_workflows = parse_config_file(args.config_file, args.repos_dir)
    workflows.extend(new_workflows)

  # Add any paths to the python path
  extra_py_paths = []
  for p in config.get("python_paths", []):
    # Assume that python_paths are in the format $REPO_OWNER/$REPO_NAME/path,
    # we need to ensure that the repo is checked out if it is different from
    # the current one, and if the repo is not kubeflow/testing (which is already
    # checked out).
    segments = p.split("/")
    if ((segments[0] != repo_owner or segments[1] != repo_name)
        and not p.startswith("kubeflow/testing")):
      logging.info("Need to clone %s/%s", segments[0], segments[1])
      util.clone_repo(os.path.join(args.repos_dir, segments[0], segments[1]),
                      segments[0], segments[1])

    path = os.path.join(args.repos_dir, p)
    extra_py_paths.append(path)

  kf_test_path = os.path.join(args.repos_dir, "kubeflow/testing/py")
  if kf_test_path not in extra_py_paths:
    logging.info("Adding %s to extra python paths", kf_test_path)
    extra_py_paths.append(kf_test_path)

  logging.info("Extra python paths: %s", ":".join(extra_py_paths))

  if not args.cloud_provider or args.cloud_provider == "gcp":
    # Create an initial version of the file with no urls
    create_started_file(args.bucket, {})

    util.maybe_activate_service_account()

    util.configure_kubectl(args.project, args.zone, args.cluster)
    util.load_kube_config()
  elif args.cloud_provider == "aws":
    create_started_file_s3(args.bucket, {})
    aws_util.aws_configure_credential()
    aws_util.load_kube_config()

  tekton_runner = tekton_client.TektonRunner()
  workflow_names = []
  tkn_names = []
  tkn_cleanup_args = []
  ui_urls = {}

  for w in workflows: # pylint: disable=too-many-nested-blocks
    # Create the name for the workflow
    # We truncate sha numbers to prevent the workflow name from being too large.
    # Workflow name should not be more than 63 characters because its used
    # as a label on the pods.
    #
    # TODO(jlewi):This should no longer be used with Tekton. For tekton
    # name should be based on generateName; we should use labels to
    # provide additional metadata info like PR number.
    workflow_name = os.getenv("JOB_NAME", "") + "-" + w.name

    # Skip this workflow if it is scoped to a different job type.
    if w.job_types and not job_type in w.job_types:
      logging.info("Skipping workflow %s because job type %s is not one of "
                   "%s.", w.name, job_type, w.job_types)
      continue

    # If we are scoping this workflow to specific directories, check if any files
    # modified match the specified regex patterns.
    dir_modified = False
    if w.include_dirs:
      for f in changed_files:
        for d in w.include_dirs:
          if fnmatch.fnmatch(f, d):
            dir_modified = True
            logging.info("Triggering workflow %s because %s in dir %s is modified.",
                         w.name, f, d)
            break
        if dir_modified:
          break

    # Only consider modified files when the job is pre or post submit, and if
    # the include_dirs stanza is defined.
    if job_type != "periodic" and w.include_dirs and not dir_modified:
      logging.info("Skipping workflow %s because no code modified in %s.",
                   w.name, w.include_dirs)
      continue

    if job_type == "presubmit":
      # When not running under prow we might not set all environment variables
      if os.getenv("PULL_NUMBER"):
        workflow_name += "-{0}".format(os.getenv("PULL_NUMBER"))
      if os.getenv("PULL_PULL_SHA"):
        workflow_name += "-{0}".format(os.getenv("PULL_PULL_SHA")[0:7])

    elif job_type == "postsubmit":
      if os.getenv("PULL_BASE_SHA"):
        workflow_name += "-{0}".format(os.getenv("PULL_BASE_SHA")[0:7])

    # Append the last 4 digits of the build number
    if os.getenv("BUILD_NUMBER"):
      workflow_name += "-{0}".format(os.getenv("BUILD_NUMBER")[-4:])

    salt = uuid.uuid4().hex[0:4]
    # Add some salt. This is mostly a convenience for the case where you
    # are submitting jobs manually for testing/debugging. Since the prow should
    # vend unique build numbers for each job.
    workflow_name += "-{0}".format(salt)
    if w.tekton_run:
      tkn_names.append(workflow_name)
    else:
      workflow_names.append(workflow_name)

    # check if ks workflow and run
    if w.app_dir:
      ks_cmd = ks_util.get_ksonnet_cmd(w.app_dir)

      # Print ksonnet version
      util.run([ks_cmd, "version"])

      # Create a new environment for this run
      env = workflow_name

      util.run([ks_cmd, "env", "add", env, "--namespace=" + get_namespace(args), "--api-spec=version:v1.8.0"],
                cwd=w.app_dir)

      util.run([ks_cmd, "param", "set", "--env=" + env, w.component,
                "name", workflow_name],
               cwd=w.app_dir)

      # Set the prow environment variables.
      prow_env = []

      names = ["JOB_NAME", "JOB_TYPE", "BUILD_ID", "BUILD_NUMBER",
               "PULL_BASE_SHA", "PULL_NUMBER", "PULL_PULL_SHA", "REPO_OWNER",
               "REPO_NAME"]
      names.sort()
      for v in names:
        if not os.getenv(v):
          continue
        prow_env.append("{0}={1}".format(v, os.getenv(v)))

      util.run([ks_cmd, "param", "set", "--env=" + env, w.component, "prow_env",
               ",".join(prow_env)], cwd=w.app_dir)
      util.run([ks_cmd, "param", "set", "--env=" + env, w.component, "namespace",
               get_namespace(args)], cwd=w.app_dir)
      util.run([ks_cmd, "param", "set", "--env=" + env, w.component, "bucket",
               args.bucket], cwd=w.app_dir)
      if args.cloud_provider == "aws":
        util.run([ks_cmd, "param", "set", "--env=" + env, w.component, "cluster_name",
                "eks-cluster-{}".format(uuid.uuid4().hex[0:8])], cwd=w.app_dir)
      if args.release:
        util.run([ks_cmd, "param", "set", "--env=" + env, w.component, "versionTag",
                  os.getenv("VERSION_TAG")], cwd=w.app_dir)

      # Set any extra params. We do this in alphabetical order to make it easier to verify in
      # the unittest.
      param_names = w.params.keys()
      if six.PY3:
        # In python3, dict_keys.sort() not work given
        # https://docs.python.org/3/whatsnew/3.0.html#views-and-iterators-instead-of-lists
        param_names = sorted(param_names)
      else:
        param_names.sort()
      for k in param_names:
        util.run([ks_cmd, "param", "set", "--env=" + env, w.component, k,
                 "{0}".format(w.params[k])], cwd=w.app_dir)

      # For debugging print out the manifest
      util.run([ks_cmd, "show", env, "-c", w.component], cwd=w.app_dir)
      util.run([ks_cmd, "apply", env, "-c", w.component], cwd=w.app_dir)

      if not args.cloud_provider or args.cloud_provider == "gcp":
        ui_url = ("http://testing-argo.kubeflow.org/workflows/kubeflow-test-infra/{0}"
                "?tab=workflow".format(workflow_name))
      elif args.cloud_provider == "aws":
        ui_url = ("http://testing-argo.kubeflow.aws.org/workflows/kubeflow-test-infra/{0}"
                "?tab=workflow".format(workflow_name))
      ui_urls[workflow_name] = ui_url
      logging.info("URL for workflow: %s", ui_url)
    elif w.tekton_run:
      pull_revision = None
      if os.getenv("PULL_NUMBER"):
        pull_revision = "refs/pull/{pull_num}/head".format(
            pull_num=os.getenv("PULL_NUMBER"))
      elif os.getenv("PULL_BASE_SHA"):
        pull_revision = os.getenv("PULL_BASE_SHA")
      else:
        pull_revision = "master"
      logging.info("Adding Tekton pipeline %s", w.name)
      try:
        pipeline_runner = tekton_client.PipelineRunner(
            w.tekton_params,
            w.kwargs.get(TEST_TARGET_ARG_NAME, w.name),
            w.tekton_run,
            args.bucket,
            repo_owner,
            repo_name,
            pull_revision)
      except (FileNotFoundError, ValueError) as e:
        logging.error("Error when starting Tekton workflow:%s\n Exception %s;\n"
                      "stacktrace:\n%s",
                      w.tekton_run, e, traceback.format_exc())
        continue
      if w.tekton_teardown:
        logging.info("Appending teardown process for Tekton pipeline %s",
                     w.name)
        pipeline_runner.append_teardown(tekton_client.PipelineRunner(
          w.tekton_teardown_params,
          w.kwargs.get(TEST_TARGET_ARG_NAME, w.name),
          w.tekton_teardown,
          args.bucket,
          repo_owner,
          repo_name,
          pull_revision))
      tekton_runner.append(pipeline_runner)
    else:
      w.kwargs["name"] = workflow_name
      w.kwargs["namespace"] = get_namespace(args)

      if TEST_TARGET_ARG_NAME not in w.kwargs:
        w.kwargs[TEST_TARGET_ARG_NAME] = w.name
        logging.info("Workflow %s doesn't set arg %s; defaulting to %s",
                     w.name, TEST_TARGET_ARG_NAME,
                     w.kwargs[TEST_TARGET_ARG_NAME])

      # TODO(https://github.com/kubeflow/testing/issues/467): We shell out
      # to e2e_tool in order to dumpy the Argo workflow to a file which then
      # reimport. We do this because importing the py_func module appears
      # to break when we have to dynamically adjust sys.path to insert
      # new paths. Setting PYTHONPATH before launching python however appears
      # to work which is why we shell out to e2e_tool.
      command = ["python", "-m", "kubeflow.testing.e2e_tool", "show",
                 w.py_func]
      for k, v in w.kwargs.items():
        # The fire module turns underscores in parameter names into hyphens
        # so we convert underscores in parameter names to hyphens
        command.append("--{0}={1}".format(k.replace("_", "-"), v))

      with tempfile.NamedTemporaryFile(delete=False) as hf:
        workflow_file = hf.name

      command.append("--output=" + hf.name)
      env = os.environ.copy()
      env["PYTHONPATH"] = ":".join(extra_py_paths)
      util.run(command, env=env)

      with open(workflow_file) as hf:
        wf_result = yaml.load(hf)

      group, version = wf_result['apiVersion'].split('/')
      k8s_co = k8s_client.CustomObjectsApi()
      workflow_name = wf_result["metadata"]["name"]
      py_func_result = k8s_co.create_namespaced_custom_object(
        group=group,
        version=version,
        namespace=wf_result["metadata"]["namespace"],
        plural='workflows',
        body=wf_result)
      logging.info("Created workflow:\n%s", yaml.safe_dump(py_func_result))

      if not args.cloud_provider or args.cloud_provider == "gcp":
        ui_url = ("http://testing-argo.kubeflow.org/workflows/kubeflow-test-infra/{0}"
                "?tab=workflow".format(workflow_name))
      elif args.cloud_provider == "aws":
        ui_url = ("http://testing-argo.kubeflow.aws.org/workflows/kubeflow-test-infra/{0}"
                "?tab=workflow".format(workflow_name))
      ui_urls[workflow_name] = ui_url
      logging.info("URL for workflow: %s", ui_url)

  if not args.cloud_provider or args.cloud_provider == "gcp":
    ui_urls.update(tekton_runner.run(
        tekton_client.ClusterInfo(args.project,
                                  TEKTON_CLUSTER_ZONE,
                                  TEKTON_CLUSTER_NAME),
        tekton_client.ClusterInfo(args.project, args.zone, args.cluster)))

    # We delay creating started.json until we know the Argo workflow URLs
    create_started_file(args.bucket, ui_urls)
  elif args.cloud_provider == "aws":
    # We delay creating started.json until we know the Argo workflow URLs
    create_started_file_s3(args.bucket, ui_urls)

  workflow_success = False
  workflow_phase = {}
  workflow_status_yamls = {}
  results = []
  tekton_results = []
  try:
    results = argo_client.wait_for_workflows(
      get_namespace(args), workflow_names,
      timeout=datetime.timedelta(minutes=180),
      status_callback=argo_client.log_status
    )
    if not args.cloud_provider or args.cloud_provider == "gcp":
      util.configure_kubectl(args.project, "us-east1-d", "kf-ci-v1")
      util.load_kube_config()
      tekton_results = tekton_runner.join()
    elif args.cloud_provider == "aws":
      aws_util.load_kube_config()
    workflow_success = True
  except util.ExceptionWithWorkflowResults as e:
    # We explicitly log any exceptions so that they will be captured in the
    # build-log.txt that is uploaded to Gubernator.
    logging.exception("Exception occurred: %s", e)
    results = e.workflow_results
    raise
  except Exception as e:
    logging.exception("Other exception: %s", e)
    raise
  finally:
    if not args.cloud_provider or args.cloud_provider == "gcp":
      util.configure_kubectl(args.project, args.zone, args.cluster)
      util.load_kube_config()
      prow_artifacts_dir = prow_artifacts.get_gcs_dir(args.bucket)
    elif args.cloud_provider == "aws":
      prow_artifacts_dir = aws_prow_artifacts.get_s3_dir(args.bucket)

    # Upload workflow status to GCS/S3.
    for r in results:
      phase = r.get("status", {}).get("phase")
      name = r.get("metadata", {}).get("name")
      workflow_phase[name] = phase
      workflow_status_yamls[name] = yaml.safe_dump(r, default_flow_style=False)
      if phase != "Succeeded":
        workflow_success = False
      logging.info("Workflow %s/%s finished phase: %s", get_namespace(args), name, phase)

      if not args.cloud_provider or args.cloud_provider == "gcp":
        for wf_name, wf_status in workflow_status_yamls.items():
          util.upload_to_gcs(
            wf_status,
            os.path.join(prow_artifacts_dir, '{}.yaml'.format(wf_name)))
      elif args.cloud_provider == "aws":
        for wf_name, wf_status in workflow_status_yamls.items():
          aws_util.upload_to_s3(
            wf_status,
            os.path.join(prow_artifacts_dir, '{}.yaml'.format(wf_name)),
            '{}.yaml'.format(wf_name))

    for r in tekton_results:
      condition = "Failed"
      name = r.get("metadata", {}).get("name")
      if r.get("status", {}).get("conditions", []):
        condition = r["status"]["conditions"][0].get("reason", "Failed")
      workflow_phase[name] = condition
      workflow_status_yamls[name] = yaml.safe_dump(r, default_flow_style=False)
      if condition != "Succeeded":
        workflow_success = False
      logging.info("Workflow %s/%s finished phase: %s",
                   args.tekton_namespace, name, condition)

    # Upload logs to GCS. No logs after this point will appear in the
    # file in gcs
    file_handler.flush()

    if not args.cloud_provider or args.cloud_provider == "gcp":
      util.upload_file_to_gcs(
        file_handler.baseFilename,
        os.path.join(prow_artifacts_dir, "build-log.txt"))
      all_tests_success = prow_artifacts.finalize_prow_job(
        args.bucket, workflow_success, workflow_phase, ui_urls)
    elif args.cloud_provider == "aws":
      aws_util.upload_file_to_s3(
        file_handler.baseFilename,
        os.path.join(prow_artifacts_dir, "build-log.txt"))
      all_tests_success = aws_prow_artifacts.finalize_prow_job_to_s3(
        args.bucket, workflow_success, workflow_phase, ui_urls
      )

  return all_tests_success

def main(unparsed_args=None):  # pylint: disable=too-many-locals
  logging.getLogger().setLevel(logging.INFO) # pylint: disable=too-many-locals
  # create the top-level parser
  parser = argparse.ArgumentParser(
    description="Submit an Argo workflow to run the E2E tests.")

  parser.add_argument(
    "--project",
    default="",
    type=str,
    help="The project containing the GKE cluster to use to run the workflow.")

  parser.add_argument(
    "--zone",
    default="",
    type=str,
    help="The zone containing the GKE cluster to use to run the workflow.")

  parser.add_argument(
    "--cluster",
    default="",
    type=str,
    help="The GKE cluster to use to run the workflow.")

  parser.add_argument(
    "--bucket",
    default="",
    type=str,
    help="The bucket to use for the Gubernator outputs.")

  parser.add_argument(
    "--config_file",
    default="",
    type=str,
    help="Yaml file containing the config.")

  parser.add_argument(
    "--repos_dir",
    default="",
    type=str,
    help="The directory where the different repos are checked out.")

  parser.add_argument(
    "--release",
    action='store_true',
    default=False,
    help="Whether workflow is for image release")

  parser.add_argument(
    "--namespace",
    default=None,
    type=str,
    help="Optional namespace to use")

  parser.add_argument(
    "--tekton_namespace",
    type=str,
    default="tektoncd",
    help="Optional Tekton namespace to use")

  ############ Other cloud provider like AWS/IBM/Arrikto
  parser.add_argument(
    "--cloud_provider",
    type=str,
    default="", ## can be "aws" / "ibm" / ....
    help="Option to enable other cloud provider functionalities aws/ibm/cisco ..."
  )

  parser.add_argument(
    "--aws_region",
    type=str,
    default="us-west-2",
    help="region containing the EKS cluster to use to run the workflow."
  )

  #############################################################################
  # Process the command line arguments.

  # Parse the args
  args = parser.parse_args(args=unparsed_args)
  # Setup a logging file handler. This way we can upload the log outputs
  # to gubernator.
  root_logger = logging.getLogger()

  with tempfile.NamedTemporaryFile(prefix="tmpRunE2eWorkflow", suffix="log") as hf:
    test_log = hf.name

  file_handler = logging.FileHandler(test_log)
  root_logger.addHandler(file_handler)
  # We need to explicitly set the formatter because it will not pick up
  # the BasicConfig.
  formatter = logging.Formatter(fmt=("%(levelname)s|%(asctime)s"
                                     "|%(pathname)s|%(lineno)d| %(message)s"),
                                datefmt="%Y-%m-%dT%H:%M:%S")
  file_handler.setFormatter(formatter)
  logging.info("Logging to %s", test_log)

  return run(args, file_handler)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  final_result = main()
  if not final_result:
    # Exit with a non-zero exit code by to signal failure to prow.
    logging.error("One or more test steps failed exiting with non-zero exit "
                  "code.")
    sys.exit(1)