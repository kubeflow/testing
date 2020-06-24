# TODO(jlewi): I think this code has to support a mix of python2 and python3
# because run_e2e_workflow.py might still be using pyhton2.
import logging
import json
import six
import fire
import os
from multiprocessing import Pool
import re
import tempfile
import traceback
from xml.etree import ElementTree as ET
import yaml

if six.PY3:
  import http
else:
  import httplib


from kubernetes import client as k8s_client # pylint: disable=wrong-import-position
from kubernetes.client import rest # pylint: disable=wrong-import-position
from retrying import retry # pylint: disable=wrong-import-position

from kubeflow.testing import prow_artifacts # pylint: disable=wrong-import-position
from kubeflow.testing import util # pylint: disable=wrong-import-position

GROUP = "tekton.dev"
VERSION = "v1alpha1"
PLURAL = "pipelineruns"

# Default namespace for running Tekton jobs.
DEFAULT_TEKTON_NAMESPACE = "kf-ci"

def log_status(workflow):
  """A callback to use with wait_for_workflow."""
  try:
    logging.info("Workflow %s in namespace %s; condition=%s",
                 workflow["metadata"]["name"],
                 workflow["metadata"]["namespace"],
                 workflow["status"]["conditions"][0]["reason"])
  except KeyError as e:
    # Ignore the error and just log the stacktrace
    # as sometimes the workflow object does not have all the fields
    # https://github.com/kubeflow/testing/issues/147
    logging.exception('KeyError: %s', e)

def handle_retriable_exception(exception):
  if isinstance(exception, rest.ApiException):
    # ApiException could store the exit code in status or it might
    # store it in HTTP response body
    # see: https://github.com/kubernetes-client/python/blob/5e512ff564c244c50cab780d821542ed56aa965a/kubernetes/client/rest.py#L289  # pylint: disable=line-too-long
    code = None
    if exception.body:
      if isinstance(exception.body, six.string_types):
        body = {}
        try:
          logging.info("Parsing ApiException body: %s", exception.body)
          body = json.loads(exception.body)
        except json.JSONDecodeError as e:
          logging.error("Error parsing body: %s", e)
      else:
        body = exception.body
      code = body.get("code")
    else:
      code = exception.status

    # UNAUTHORIZED and FORBIDDEN errors can be an indication we need to
    # refresh credentials
    logging.info("ApiException code=%s", code)
    # TODO(jlewi): In python3 we can switch to using http.HttpStatusCode
    codes = []
    if six.PY3:
      codes = [http.HTTPStatus.UNAUTHORIZED,
               http.HTTPStatus.FORBIDDEN,
               http.HTTPStatus.GATEWAY_TIMEOUT]
    else:
      codes = [httplib.UNAUTHORIZED, httplib.FORBIDDEN, httplib.GATEWAY_TIMEOUT]
    if code in codes:
      # Due to https://github.com/kubernetes-client/python-base/issues/59,
      # we need to reload the kube config (which refreshes the GCP token).
      # TODO(richardsliu): Remove this workaround when the k8s client issue
      # is resolved.
      util.load_kube_config()
      return True

  logging.info("Retry on exception: %s; stack trace:\n%s", exception,
               traceback.format_exc())
  return not isinstance(exception, util.TimeoutError)


# Wait 2^x * 1 second between retries up to a max of 10 seconds between
# retries.
# Retry for a maximum of 5 minutes.
# We use a large timeout because we are seeing lots of unavailability with
# our K8s master in our test cluster
# See:
# https://github.com/kubeflow/testing/issues/169
# https://github.com/kubeflow/testing/issues/171
@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000,
       stop_max_delay=30*60*1000,
       retry_on_exception=handle_retriable_exception)
def get_namespaced_custom_object_with_retries(namespace, name):
  """Call get_namespaced_customer_object API with retries.
  Args:
    namespace: namespace for the workflow.
    name: name of the workflow.
  """
  # Due to https://github.com/kubernetes-client/python-base/issues/59,
  # we need to recreate the API client since it may contain stale auth
  # tokens.
  # TODO(richardsliu): Remove this workaround when the k8s client issue
  # is resolved.
  client = k8s_client.ApiClient()
  crd_api = k8s_client.CustomObjectsApi(client)
  result = crd_api.get_namespaced_custom_object(
    GROUP, VERSION, namespace, PLURAL, name)
  log_status(result)
  condition = result["status"]["conditions"][0]["reason"]
  if not condition in ["Failed", "Succeeded"]:
    raise ValueError("Waiting for {0}/{1} to finish".format(namespace, name))

  return result

# TODO(jlewi): Why are we setting test_target_name and unit_path?
# I think that was some attempt to ensure uniqueness of the test class names
# and GCS path when running multiple workflows from the same prow test.
# Can this be done in the Pipeline and Task resources by appending
# unique subdirectories to the paths?
def load_tekton_run(params, test_target_name, tekton_run, # pylint: disable=too-many-branches
                    bucket, repo_owner, repo_under_test, pull_revision):
  """Load Tekton configs and override information from Prow.
  Args:
    params: Extra parameters to be passed into Tekton pipelines.
    test_target_name: test target name as classname in JUNIT.
    tekton_run: File path to the PipelineRun config.
    bucket: GCS bucket to write artifacts to.
  """
  with open(tekton_run) as f:
    config = yaml.load(f)
    if config.get("kind", "") != "PipelineRun":
      raise ValueError("Invalid config (not PipelineRun): " + config)

  if not "generateName" in config["metadata"]:
    raise ValueError("TektonPipeline is missing generateName")

  logging.info("Reading Tekton PipelineRun config: %s",
               config["metadata"]["generateName"])

  workflow_name = config["metadata"]["generateName"]
  artifacts_gcs = prow_artifacts.get_gcs_dir(bucket)
  junit_path = "artifacts/junit_{run_name}".format(run_name=workflow_name)

  args = {
      "test-target-name": test_target_name,
      "artifacts-gcs": artifacts_gcs,
      "junit-path": junit_path,
  }
  for p in params:
    args[p["name"]] = p["value"]
  for param in config.get("spec", {}).get("params", []):
    n = param.get("name", "")
    v = param.get("value", "")
    if n and v and not n in args:
      args[n] = v

  config["spec"]["params"] = []
  for n in args:
    logging.info("Writing Tekton param: %s -> %s", n, args[n])
    config["spec"]["params"].append({
      "name": n,
      "value": args[n],
    })

  # Points to the revision under test.
  repo_url = "https://github.com/{owner}/{name}.git".format(
      owner=repo_owner,
      name=repo_under_test)
  replacing_param = [
      {"name": "url", "value": repo_url},
      {"name": "revision", "value": pull_revision},
  ]

  job_type = os.getenv("JOB_TYPE", "").lower()

  if job_type in ["presubmit", "postsubmit"]:
    logging.info("Job is type %s; looking for url %s", job_type, repo_url)
    foundRepo = False
    for resource in config["spec"].get("resources", []):
      if resource.get("resourceSpec", {}).get("type", "") != "git":
        pass
      for param in resource.get("resourceSpec", {}).get("params", []):
        if param.get("name", "") != "url":
          continue
        if param.get("value", "") == repo_url:
          foundRepo = True
          resource["resourceSpec"]["params"] = replacing_param
          break
    if not foundRepo:
      raise ValueError(("The TektonPipelineRun is missing a pipeline git "
                        "resource that matches the repo being tested by "
                        "prow. The pipeline parameters must include "
                        "a git resource whose URL is {0}".format(repo_url)))
  else:
    logging.info("Job is type %s; not looking for repo", job_type)

  return config

class PipelineRunner(object): # pylint: disable=useless-object-inheritance
  """Runs and wait for the Tekton pipeline to finish.

  The name for the pipeline will be generated using generateName
  """
  def __init__(self, params, test_target_name, config_path, bucket, # pylint: disable=too-many-arguments
               repo_owner, repo_under_test, pull_revision): # pylint: disable=too-many-arguments
    # Name will be dynamically generated by generateName
    self.name = None
    self.config = load_tekton_run(params, test_target_name, config_path,
                                  bucket, repo_owner, repo_under_test,
                                  pull_revision)
    self.namespace = self.config["metadata"].get("namespace",
                                                 DEFAULT_TEKTON_NAMESPACE)
    self.teardown_runner = None

  def run(self):
    """Runs the Tekton pipeline async.
    """
    client = k8s_client.ApiClient()
    crd_api = k8s_client.CustomObjectsApi(client)

    group, version = self.config["apiVersion"].split("/")
    try:
      result = crd_api.create_namespaced_custom_object(
          group=group,
          version=version,
          namespace=self.namespace,
          plural=PLURAL,
          body=self.config)
      logging.info("Created workflow:\n%s", yaml.safe_dump(result))
    except rest.ApiException as e:
      logging.error("Could not create workflow: %s")
      if e.body:
        body = None
        if isinstance(e.body, six.string_types):
          body = {}
          try:
            logging.info("Parsing ApiException body: %s", e.body)
            body = json.loads(e.body)
          except json.JSONDecodeError as json_e:
            logging.error("Error parsing body: %s", json_e)
        else:
          body = e.body
        logging.error("Could not create workflow; %s", body)
      else:
        logging.error("Could not create workflow: %s", e)
      raise

    self.name = result.get("metadata", {}).get("name")
    logging.info("Submitted Tekton Pipeline %s.%s", self.namespace, self.name)
    return result

  def append_teardown(self, runner):
    self.teardown_runner = runner

  @property
  def ui_url(self):
    return ("https://kf-ci-v1.endpoints.kubeflow-ci.cloud.goog/tekton/#/namespaces/"
            "{0}/pipelineruns/{1}".format(self.namespace, self.name))

  def wait(self):
    """Wait for the workflow to finish.
    """
    r = [get_namespaced_custom_object_with_retries(self.namespace, self.name)]
    if not self.teardown_runner:
      logging.info("Skipping teardown process for %s, no teardown process found",
                   self.name)
      return r

    self.teardown_runner.run()
    r.extend(self.teardown_runner.wait())
    return r

# Simple function to invoke wait. Pool is not able to take as input lambda
# functions.
def wait_(runner):
  return runner.wait()

class ClusterInfo(object): # pylint: disable=useless-object-inheritance
  """Simple data carrier to provide access to the cluster running test.
  """
  def __init__(self, project, zone, cluster_name):
    self.project = project
    self.zone = zone
    self.cluster_name = cluster_name

class TektonRunner(object): # pylint: disable=useless-object-inheritance
  """Runs Tekton pipelines and wait for all the workflows to finish.
  """
  def __init__(self):
    self.workflows = []

  def append(self, runner):
    self.workflows.append(runner)

  def run(self, tekton_cluster_info, current_cluster_info):
    """Kicks off all the Tekton pipelines.
    Args:
      tekton_cluster_info: ClusterInfo having the info to run pipelines on.
      Tekton runs on different cluster right now.
      current_cluster_info: Current cluster info.

    Returns:
      a list of UI urls.
    """
    urls = dict()
    try:
      # Currently only tekton tests run in kf-ci-v1.
      util.configure_kubectl(tekton_cluster_info.project,
                             tekton_cluster_info.zone,
                             tekton_cluster_info.cluster_name)
      # util.configure_kubectl(project, "us-east1-d", "kf-ci-v1")
      util.load_kube_config()

      for w in self.workflows:
        w.run()
        urls[w.name] = w.ui_url
        if w.teardown_runner:
          urls[w.teardown_runner.name] = w.teardown_runner.ui_url
        logging.info("URL for workflow: %s", w.ui_url)
    except Exception as e: # pylint: disable=broad-except
      logging.error("Error when starting Tekton workflow: %s;\nstacktrace:\n%s",
                    e, traceback.format_exc())
    finally:
      # Restore kubectl
      util.configure_kubectl(current_cluster_info.project,
                             current_cluster_info.zone,
                             current_cluster_info.cluster_name)
      util.load_kube_config()

    return urls

  def join(self):
    """Join all the running pipelines and returns the results.
    """
    if not self.workflows:
      return []
    p = Pool(len(self.workflows))
    results = p.map(wait_, self.workflows)
    flattened = []
    for r in results:
      flattened.extend(r)
    return flattened

class CLI(object): # pylint: disable=useless-object-inheritance
  @staticmethod
  def upload(artifacts_dir, output_gcs):
    """Upload directory to GCS.

    The code parses all junit files and if there is any test failures
    raises an exception. The purpose of this is to convert test failures
    into task and thus pipeline failures. run_e2e_workflow.py will
    then report the GitHub status check as failed because the pipeline
    didn't run successfully.

    Args:
      artifacts_dir: Directory containing artifacts
      outputs_gcs: GCS path to upload to. If empty no artifacts will
        be uploaded.
    """
    logging.info("Uploading %s to GCS %s", artifacts_dir, output_gcs)
    util.maybe_activate_service_account()
    util.run(["gsutil", "-m", "rsync", "-r", artifacts_dir, output_gcs])

  @staticmethod
  def junit_parse_and_upload(artifacts_dir, output_gcs):
    """Parse the junit file and upload it to GCS.

    The code parses all junit files and if there is any test failures
    raises an exception. The purpose of this is to convert test failures
    into task and thus pipeline failures. run_e2e_workflow.py will
    then report the GitHub status check as failed because the pipeline
    didn't run successfully.

    Args:
      artifacts_dir: Directory containing artifacts
      outputs_gcs: GCS path to upload to. If empty no artifacts will
        be uploaded.
    """
    CLI.upload(artifacts_dir, output_gcs)

    logging.info("Walking through directory: %s", artifacts_dir)
    junit_pattern = re.compile(r"junit.*\.xml")
    failed_num = 0
    found_xml = False
    for root, _, files in os.walk(artifacts_dir):
      for filename in files:
        if not junit_pattern.match(filename):
          continue
        found_xml = True
        logging.info("Parsing JUNIT: %s", filename)
        tree = ET.parse(os.path.join(root, filename))
        root = tree.getroot()
        failed_num = int(root.attrib.get(
            "errors", "0")) + int(root.attrib.get("failures", "0"))

        for testcase in root:
          testname = testcase.attrib.get("name", "unknown-test")
          has_failure = False
          for failure in testcase:
            has_failure = True
            logging.error("%s has failure: %s",
                          testname,
                          failure.attrib.get("message", "message not found"))
          if not has_failure:
            logging.info("%s has passed all the tests.", testname)

    if not found_xml:
      raise ValueError("No JUNIT artifats found in " + artifacts_dir)
    if failed_num:
      raise ValueError(
          "This task is failed with {0} errors/failures.".format(failed_num))

  @staticmethod
  def create_image_file(image_name, digest_file, output):
    """Create a YAML file containing the URL of the built image.

    Args:
      image_name: Url of the image; e.g. gcr.io/myimage/someimage
      digest_file: A file containing the digest of the image.
        This is the file outputted by Kaniko's to --digest-file"
      output: The path to write to. Can be GCS.
    """
    with open(digest_file) as hf:
      digest = hf.read()
    digest = digest.strip()

    full_image = "{0}@{1}".format(image_name, digest)
    logging.info(f"Full digest: {full_image}")

    contents = {
      "image": full_image
    }

    is_gcs = output.lower().startswith("gs://")

    if is_gcs:
      with tempfile.NamedTemporaryFile() as hf:
        local_file = hf.name
    else:
      local_file = output

    logging.info(f"Writing to {local_file}")
    with open(local_file, "w") as hf:
      yaml.dump(contents, hf)

    if is_gcs:
      util.upload_file_to_gcs(local_file, output)

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(CLI)
