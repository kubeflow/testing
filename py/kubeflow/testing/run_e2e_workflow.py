"""Run the E2E workflow.

This script submits Argo workflows to run the E2E tests and waits for
them to finish. It is intended to be invoked by prow jobs.

It requires the workflow to be expressed as a ksonnet app.

The script can take a config file via --config_file.
The --config_file is expected to be a YAML file as follows:

workflows:
  - name: e2e-test
    app_dir: tensorflow/k8s/test/workflows
    component: workflows

  - name: lint
    app_dir: kubeflow/kubeflow/testing/workflows
    component: workflows

app_dir is expected to be in the form of
{REPO_OWNER}/{REPO_NAME}/path/to/ksonnet/app

component is the name of the ksonnet component corresponding
to the workflow to launch.

The script expects that the directories
{repos_dir}/{app_dir} exists. Where repos_dir is provided
as a command line argument.
"""

import argparse
import datetime
import logging
from kubernetes import client as k8s_client
import os
import tempfile
from kubeflow.testing import argo_client
from kubeflow.testing import prow_artifacts
from kubeflow.testing import util
import uuid
import sys
import yaml

# The namespace to launch the Argo workflow in.
def get_namespace(args):
  if args.release:
    return "kubeflow-releasing"
  return "kubeflow-test-infra"

class WorkflowComponent(object):
  """Datastructure to represent a ksonnet component to submit a workflow."""

  def __init__(self, name, app_dir, component, params):
    self.name = name
    self.app_dir = app_dir
    self.component = component
    self.params = params

def _get_src_dir():
  return os.path.abspath(os.path.join(__file__, "..",))

def create_started_file(bucket):
  """Create the started file in gcs for gubernator."""
  contents = prow_artifacts.create_started()

  target = os.path.join(prow_artifacts.get_gcs_dir(bucket), "started.json")
  util.upload_to_gcs(contents, target)

def parse_config_file(config_file, root_dir):
  with open(config_file) as hf:
    results = yaml.load(hf)

  components = []
  for i in results["workflows"]:
    components.append(WorkflowComponent(
      i["name"], os.path.join(root_dir, i["app_dir"]), i["component"], i.get("params", {})))
  return components

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
  # Print ksonnet version
  util.run(["ks", "version"])
  if args.release:
    generate_env_from_head(args)
  workflows = []
  if args.config_file:
    workflows.extend(parse_config_file(args.config_file, args.repos_dir))

  if args.app_dir and args.component:
    # TODO(jlewi): We can get rid of this branch once all repos are using a prow_config.xml file.
    workflows.append(WorkflowComponent("legacy", args.app_dir, args.component, {}))
  create_started_file(args.bucket)

  util.maybe_activate_service_account()

  util.configure_kubectl(args.project, args.zone, args.cluster)
  util.load_kube_config()

  api_client = k8s_client.ApiClient()
  workflow_names = []
  ui_urls = {}

  for w in workflows:
    # Create the name for the workflow
    # We truncate sha numbers to prevent the workflow name from being too large.
    # Workflow name should not be more than 63 characters because its used
    # as a label on the pods.
    workflow_name = os.getenv("JOB_NAME") + "-" + w.name
    job_type = os.getenv("JOB_TYPE")
    if job_type == "presubmit":
      workflow_name += "-{0}".format(os.getenv("PULL_NUMBER"))
      workflow_name += "-{0}".format(os.getenv("PULL_PULL_SHA")[0:7])

    elif job_type == "postsubmit":
      workflow_name += "-{0}".format(os.getenv("PULL_BASE_SHA")[0:7])

    workflow_name += "-{0}".format(os.getenv("BUILD_NUMBER"))

    salt = uuid.uuid4().hex[0:4]
    # Add some salt. This is mostly a convenience for the case where you
    # are submitting jobs manually for testing/debugging. Since the prow should
    # vend unique build numbers for each job.
    workflow_name += "-{0}".format(salt)

    workflow_names.append(workflow_name)
    # Create a new environment for this run
    env = workflow_name

    util.run(["ks", "env", "add", env], cwd=w.app_dir)

    util.run(["ks", "param", "set", "--env=" + env, w.component,
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

    util.run(["ks", "param", "set", "--env=" + env, w.component, "prow_env", ",".join(prow_env)],
             cwd=w.app_dir)
    util.run(["ks", "param", "set", "--env=" + env, w.component, "namespace", get_namespace(args)],
             cwd=w.app_dir)
    util.run(["ks", "param", "set", "--env=" + env, w.component, "bucket", args.bucket],
             cwd=w.app_dir)
    if args.release:
      util.run(["ks", "param", "set", "--env=" + env, w.component, "versionTag",
                os.getenv("VERSION_TAG")], cwd=w.app_dir)

    # Set any extra params. We do this in alphabetical order to make it easier to verify in
    # the unittest.
    param_names = w.params.keys()
    param_names.sort()
    for k in param_names:
      util.run(["ks", "param", "set", "--env=" + env, w.component, k, "{0}".format(w.params[k])],
               cwd=w.app_dir)

    # For debugging print out the manifest
    util.run(["ks", "show", env, "-c", w.component], cwd=w.app_dir)
    util.run(["ks", "apply", env, "-c", w.component], cwd=w.app_dir)

    ui_url = ("http://testing-argo.kubeflow.org/workflows/kubeflow-test-infra/{0}"
              "?tab=workflow".format(workflow_name))
    ui_urls[workflow_name] = ui_url
    logging.info("URL for workflow: %s", ui_url)

  success = True
  workflow_phase = {}
  try:
    results = argo_client.wait_for_workflows(api_client, get_namespace(args),
                                             workflow_names,
                                             status_callback=argo_client.log_status)
    for r in results:
      phase = r.get("status", {}).get("phase")
      name = r.get("metadata", {}).get("name")
      workflow_phase[name] = phase
      if phase != "Succeeded":
        success = False
      logging.info("Workflow %s/%s finished phase: %s", get_namespace(args), name, phase)
  except util.TimeoutError:
    success = False
    logging.error("Time out waiting for Workflows %s to finish", ",".join(workflow_names))
  except Exception as e:
    # We explicitly log any exceptions so that they will be captured in the
    # build-log.txt that is uploaded to Gubernator.
    logging.error("Exception occurred: %s", e)
    raise
  finally:
    success = prow_artifacts.finalize_prow_job(args.bucket, success, workflow_phase, ui_urls)

    # Upload logs to GCS. No logs after this point will appear in the
    # file in gcs
    file_handler.flush()
    util.upload_file_to_gcs(
      file_handler.baseFilename,
      os.path.join(prow_artifacts.get_gcs_dir(args.bucket), "build-log.txt"))

  return success

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

  # TODO(jlewi): app_dir and component predate the use of a config
  # file we should consider getting rid of them once all repos
  # have been updated to run multiple workflows.
  parser.add_argument(
    "--app_dir",
    type=str,
    default="",
    help="The directory where the ksonnet app is stored.")

  parser.add_argument(
    "--component",
    type=str,
    default="",
    help="The ksonnet component to use.")

  parser.add_argument(
    "--release",
    action='store_true',
    default=False,
    help="Whether workflow is for image release")

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
