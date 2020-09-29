"""Utilities used by our python scripts for building and releasing."""
import datetime
import logging
import multiprocessing
import os
import re
import six
import subprocess
import time
import yaml

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.config import kube_config
from kubernetes.client import configuration as kubernetes_configuration

import boto3

# Default name for the repo organization and name.
# This should match the values used in Go imports.
MASTER_REPO_OWNER = "tensorflow"
MASTER_REPO_NAME = "k8s"

# How long to wait in seconds for requests to the ApiServer
TIMEOUT = 120


def save_process_output(command,
                        cwd=None,
                        output=None):

  content = subprocess.check_output(command, cwd=cwd).decode("utf-8")

  try:
    with open(output, 'w') as f:
      f.write(content)
      print("Succeed in saving contents in {}".format(output))
  except FileNotFoundError:
    print("Failed in saving contents in {}".format(output))



def run(command,
        cwd=None,
        env=None,
        polling_interval=datetime.timedelta(seconds=1)):
  """Run a subprocess.

  Any subprocess output is emitted through the logging modules.

  Returns:
    output: A string containing the output.
  """
  logging.info("Running: %s \ncwd=%s", " ".join(command), cwd)

  if not env:
    env = os.environ
  else:
    keys = sorted(env.keys())

    lines = []
    for k in keys:
      lines.append("{0}={1}".format(k, env[k]))
    logging.info("Running: Environment:\n%s", "\n".join(lines))

  process = subprocess.Popen(
    command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

  logging.info("Subprocess output:\n")
  output = []
  while process.poll() is None:
    process.stdout.flush()
    for line in iter(process.stdout.readline, b''):
      if six.PY2:
        line = line.strip()
      else:
        line = line.decode().strip()

      output.append(line)
      logging.info(line)

    time.sleep(polling_interval.total_seconds())

  process.stdout.flush()
  for line in iter(process.stdout.readline, b''):
    if six.PY2:
      line = line.strip()
    else:
      line = line.decode().strip()
    output.append(line)
    logging.info(line)

  if process.returncode != 0:
    raise subprocess.CalledProcessError(
      process.returncode, "cmd: {0} exited with code {1}".format(
        " ".join(command), process.returncode), "\n".join(output))

  return "\n".join(output)


# TODO(jlewi): We should update callers to use run and just delete this function.
def run_and_output(*args, **argv):
  return run(*args, **argv)


def combine_repos(list_of_repos):
  """Builds a dictionary of repo owner/names to commit hashes.

  Args:
    list_of_repos: A list of repos to checkout, each one in the format of
      "owner/name@commit". Later values override earlier ones.
  Returns:
    repos: A dictionary of repository names to commit hashes.
  """

  # Convert list_of_repos to a dictionary where key is "repo_owner/repo_name"
  # and value is the commit hash. By convention, values that appear later in
  # the list would override earlier ones.
  repos = {}
  for r in list_of_repos:
    parts = r.split('@')
    repos[parts[0]] = parts[1]

  return repos

def clone_repo(dest,
               repo_owner=MASTER_REPO_OWNER,
               repo_name=MASTER_REPO_NAME,
               sha=None,
               branches=None):
  """Clone the repo,

  Args:
    dest: This is the root path for the training code.
    repo_owner: The owner for github organization.
    repo_name: The repo name.
    sha: The sha number of the repo.
    branches: (Optional): One or more branches to fetch. Each branch be specified
      as "remote:local". If no sha is provided
      we will checkout the last branch provided. If a sha is provided we
      checkout the provided sha.

  Returns:
    dest: Directory where it was checked out
    sha: The sha of the code.
  """
  # Clone mlkube
  repo = "https://github.com/{0}/{1}.git".format(repo_owner, repo_name)
  logging.info("repo %s", repo)

  # TODO(jlewi): How can we figure out what branch
  run(["git", "clone", repo, dest])

  if branches:
    for b in branches:
      run(
        [
          "git",
          "fetch",
          "origin",
          b,
        ], cwd=dest)

    if not sha:
      b = branches[-1].split(":", 1)[-1]
      run(
        [
          "git",
          "checkout",
          b,
        ], cwd=dest)

  if sha:
    run(["git", "checkout", sha], cwd=dest)

  # Get the actual git hash.
  # This ensures even for periodic jobs which don't set the sha we know
  # the version of the code tested.
  sha = run_and_output(["git", "rev-parse", "HEAD"], cwd=dest)

  return dest, sha


def install_go_deps(src_dir):
  """Run glide to install dependencies."""
  # Install dependencies
  run(["glide", "install", "--strip-vendor"], cwd=src_dir)


def to_s3_uri(bucket, path):
  """Convert bucket and path to a S3 URI."""
  return "s3://" + os.path.join(bucket, path)


# pylint: disable=too-many-arguments
def wait_for_cr_condition(client,
                          group,
                          plural,
                          version,
                          namespace,
                          name,
                          expected_condition,
                          timeout=datetime.timedelta(minutes=10),
                          polling_interval=datetime.timedelta(seconds=30),
                          status_callback=None):
  """Waits until any of the specified conditions occur for the specified
     custom resource.

  Args:
    client: K8s api client.
    group: Resource group.
    plural: Resource plural
    namespace: namespace for the job.
    name: Name of the job.
    expected_condition: A list of conditions. Function waits until any of the
      supplied conditions is reached.
    timeout: How long to wait for the job.
    polling_interval: How often to poll for the status of the job.
    status_callback: (Optional): Callable. If supplied this callable is
      invoked after we poll the job. Callable takes a single argument which
      is the job.
  """
  crd_api = k8s_client.CustomObjectsApi(client)
  end_time = datetime.datetime.now() + timeout
  while True:
    # By setting async_req=True ApiClient returns multiprocessing.pool.AsyncResult
    # If we don't set async_req=True then it could potentially block forever.
    thread = crd_api.get_namespaced_custom_object(
      group, version, namespace, plural, name, async_req=True)

    # Try to get the result but timeout.
    results = None
    try:
      results = thread.get(TIMEOUT)
    except multiprocessing.TimeoutError:
      logging.error("Timeout trying to get TFJob.")
    except Exception as e:
      logging.error("There was a problem waiting for Job %s.%s; Exception; %s",
                    name, name, e)
      raise

    if results:
      if status_callback:
        status_callback(results)

      # If we poll the CRD quick enough status won't have been set yet.
      conditions = results.get("status", {}).get("conditions", [])
      # Conditions might have a value of None in status.
      conditions = conditions or []
      for c in conditions:
        if c.get("type", "") in expected_condition:
          return results

    if datetime.datetime.now() + polling_interval > end_time:
      raise JobTimeoutError(
        "Timeout waiting for job {0} in namespace {1} to enter one of the "
        "conditions {2}.".format(name, namespace, conditions), results)

    time.sleep(polling_interval.seconds)

  # Linter complains if we don't have a return statement even though
  # this code is unreachable.
  return None


def wait_for_operation(client,
                       project,
                       zone,
                       op_id,
                       timeout=datetime.timedelta(hours=1),
                       polling_interval=datetime.timedelta(seconds=5)):
  """Wait for the specified operation to complete.

  Args:
    client: Client for the API that owns the operation.
    project: project
    zone: Zone. Set to none if its a global operation
    op_id: Operation id.
    timeout: A datetime.timedelta expressing the amount of time to wait before
      giving up.
    polling_interval: A datetime.timedelta to represent the amount of time to
      wait between requests polling for the operation status.

  Returns:
    op: The final operation.

  Raises:
    TimeoutError: if we timeout waiting for the operation to complete.
  """
  endtime = datetime.datetime.now() + timeout
  while True:
    if zone:
      op = client.projects().zones().operations().get(
        projectId=project, zone=zone, operationId=op_id).execute()
    else:
      op = client.globalOperations().get(
        project=project, operation=op_id).execute()

    status = op.get("status", "")
    # Need to handle other status's
    if status == "DONE":
      return op
    if datetime.datetime.now() > endtime:
      raise TimeoutError(
        "Timed out waiting for op: {0} to complete.".format(op_id))
    time.sleep(polling_interval.total_seconds())

  # Linter complains if we don't have a return here even though its unreachable.
  return None


def wait_for_deployment(api_client,
                        namespace,
                        name,
                        timeout_minutes=2,
                        replicas=1):
  """Wait for deployment to be ready.

  Args:
    api_client: K8s api client to use.
    namespace: The name space for the deployment.
    name: The name of the deployment.
    timeout_minutes: Timeout interval in minutes.
    replicas: Number of replicas that must be running.

  Returns:
    deploy: The deploy object describing the deployment.

  Raises:
    TimeoutError: If timeout waiting for deployment to be ready.
  """
  # Wait for tiller to be ready
  end_time = datetime.datetime.now() + datetime.timedelta(
    minutes=timeout_minutes)

  ext_client_apps = k8s_client.AppsV1Api(api_client)

  while datetime.datetime.now() < end_time:
    deploy = ext_client_apps.read_namespaced_deployment(name, namespace)
    # ready_replicas could be None
    if (deploy.status.ready_replicas and
        deploy.status.ready_replicas >= replicas):
      logging.info("Deployment %s in namespace %s is ready", name, namespace)
      return deploy
    logging.info("Waiting for deployment %s in namespace %s", name, namespace)
    time.sleep(10)

  logging.error("Timeout waiting for deployment %s in namespace %s to be "
                "ready", name, namespace)
  run(["kubectl", "describe", "deployment", "-n", namespace, name])
  raise TimeoutError(
    "Timeout waiting for deployment {0} in namespace {1}".format(
      name, namespace))


def wait_for_job(api_client,
                 namespace,
                 name,
                 timeout=datetime.timedelta(minutes=30)):
  """Wait for a Kubernetes batch job to finish.

  Args:
    api_client: K8s api client to use.
    namespace: The name space for the deployment.
    name: The name of the deployment.
    timeout: Timeout for job

  Returns:
    job: The kubernetes batch job object

  Raises:
    TimeoutError: If timeout waiting for deployment to be ready.
  """
  batch_api = k8s_client.BatchV1Api(api_client)

  end_time = datetime.datetime.now() + timeout
  while datetime.datetime.now() < end_time:
    job = batch_api.read_namespaced_job(name, namespace)

    if not job.status.conditions:
      logging.info("Job missing condition")
      time.sleep(10)
      continue

    last_condition = job.status.conditions[-1]
    if last_condition.type in ["Failed", "Complete"]:
      logging.info("Job %s.%s has condition %s", namespace, name,
                   last_condition.type)
      return job

    logging.info("Waiting for job %s.%s", namespace, name)
    time.sleep(10)
  logging.error("Timeout waiting for job %s.%s to finish.", namespace, name)
  run(["kubectl", "describe", "job", "-n", namespace, name])
  raise TimeoutError(
    "Timeout waiting for job {0}.{1} to finish".format(
      namespace, name))


def wait_for_jobs_with_label(api_client,
                             namespace,
                             label_filter,
                             timeout=datetime.timedelta(minutes=30)):
  """Wait for all jobs with the specified label to finish.

  Args:
    api_client: K8s api client to use.
    namespace: The name space for the deployment.
    label_filter: A label filter expression; e.g. "group=somevalue"
    timeout: Timeout for jobs

  Returns:
    job: The kubernetes batch job object

  Raises:
    TimeoutError: If timeout waiting for deployment to be ready.
  """
  batch_api = k8s_client.BatchV1Api(api_client)

  end_time = datetime.datetime.now() + timeout
  while datetime.datetime.now() < end_time:
    jobs = batch_api.list_namespaced_job(namespace, label_selector=label_filter)

    if not jobs.items:
      raise ValueError("No jobs found in namespace {0} with labels {1}".format(
                       namespace, label_filter))

    all_done = True
    done = 0
    not_done = 0
    for job in jobs.items:
      if not job.status.conditions:
        logging.info("Job %s.%s missing condition", job.metadata.namespace,
                     job.metadata.name)
        all_done = False
        not_done += 1
        continue

      last_condition = job.status.conditions[-1]
      if last_condition.type in ["Failed", "Complete"]:
        logging.info("Job %s.%s has condition %s", job.metadata.namespace,
                     job.metadata.name, last_condition.type)
        done += 1

    if all_done:
      logging.info("%s of %s jobs finished", len(jobs.items), len(jobs.items))
      return jobs

    if not all_done:
      logging.info("Waiting for job %s of %s jobs to finish", not_done,
                   not_done + done)
      time.sleep(10)

  message = ("Timeout waiting for jobs to finish; {0} of {1} "
             "not finished.").format(not_done, not_done + done)
  logging.error(message)
  raise TimeoutError(message)


def check_secret(api_client, namespace, name):
  """Check for secret existance.

  Args:
    api_client: K8s api client to use.
    namespace: The namespace for the secret.
    name: The name of the secret.

  Returns:
    secret: The secret object describing the deployment.

  Raises:
    TimeoutError: If timeout waiting for deployment to be ready.
  """

  core_client = k8s_client.CoreV1Api(api_client)

  try:
    secret = core_client.read_namespaced_secret(name, namespace)
    logging.info("Secret %s exists in namespace %s", name, namespace)
  except Exception:
    raise RuntimeError(
      "Error checking secret {0} in namespace {1}".format(
        name, namespace))
  return secret


def wait_for_statefulset(api_client, namespace, name):
  """Wait for statefulset to be ready.

  Args:
    api_client: K8s api client to use.
    namespace: The name space for the deployment.
    name: The name of the stateful set.

  Returns:
    deploy: The deploy object describing the deployment.

  Raises:
    TimeoutError: If timeout waiting for deployment to be ready.
  """
  # Wait for tiller to be ready
  end_time = datetime.datetime.now() + datetime.timedelta(minutes=2)

  apps_client = k8s_client.AppsV1Api(api_client)

  while datetime.datetime.now() < end_time:
    stateful = apps_client.read_namespaced_stateful_set(name, namespace)
    if stateful.status.ready_replicas and stateful.status.ready_replicas >= 1:
      logging.info("Statefulset %s in namespace %s is ready", name, namespace)
      return stateful
    logging.info("Waiting for Statefulset %s in namespace %s", name, namespace)
    time.sleep(10)

    run(["kubectl", "describe", "statefulset", "-n", namespace, name])
  logging.error("Timeout waiting for statefulset %s in namespace %s to be "
                "ready", name, namespace)
  raise TimeoutError(
    "Timeout waiting for statefulset {0} in namespace {1}".format(
      name, namespace))


def wait_for_gpu_driver_install(api_client,
                                timeout=datetime.timedelta(minutes=10)):
  """Wait until some nodes are available with GPUs."""

  end_time = datetime.datetime.now() + timeout
  api = k8s_client.CoreV1Api(api_client)
  while datetime.datetime.now() <= end_time:
    nodes = api.list_node()
    for n in nodes.items:
      if n.status.capacity.get("nvidia.com/gpu", 0) > 0:
        logging.info("GPUs are available.")
        return
    logging.info("Waiting for GPUs to be ready.")
    time.sleep(15)
  logging.error("Timeout waiting for GPU nodes to be ready.")
  raise TimeoutError("Timeout waiting for GPU nodes to be ready.")


# TODO(jlewi): TimeoutError should be built in in python3 so once
# we migrate to Python3 we should be able to get rid of this.
class TimeoutError(Exception):  # pylint: disable=redefined-builtin
  """An error indicating an operation timed out."""


class ExceptionWithWorkflowResults(Exception):
  def __init__(self, message, workflow_results):
    super(ExceptionWithWorkflowResults, self).__init__(message)
    self.workflow_results = workflow_results


S3_REGEX = re.compile("s3://([^/]*)(/.*)?")


def split_s3_uri(s3_uri):
  """Split a S3 URI into bucket and path."""
  m = S3_REGEX.match(s3_uri)
  bucket = m.group(1)
  path = ""
  if m.group(2):
    path = m.group(2).lstrip("/")
  return bucket, path


def load_kube_credentials():
  """Load credentials to talk to the K8s APIServer.

  There are a couple cases we need to handle

  1. Running locally - use KubeConfig
  2. Running in a pod - use the service account token token to talk to
     the K8s API server
  3. Running in a pod and talking to a different Kubernetes cluster
     in which case load from kubeconfig.

  """

  if os.getenv("KUBECONFIG"):
    logging.info("Environment variable KUBECONFIG=%s; loading credentials from "
                 "it.", os.getenv("KUBECONFIG"))
    load_kube_config(persist_config=False)
    return

  if is_in_cluster():
    logging.info("Using incluster configuration for K8s client")
    k8s_config.load_incluster_config()
    return

  logging.info("Attempting to load credentials from default KUBECONFIG file")
  load_kube_config(persist_config=False)

# TODO(jlewi): This was originally a work around for
# https://github.com/kubernetes-incubator/client-python/issues/339.
#
# There was a fix (see issue) that sets the scope but userinfo.email scope
# wasn't included. Which I think will cause problems see
# https://github.com/kubernetes-client/python-base/issues/54
#
# So as a work around we use this function to allow us to specify the scopes.
#
# This function is based on
# https://github.com/kubernetes-client/python-base/blob/master/config/kube_config.py#L331
# we modify it though so that we can pass through the function to get credentials.
def load_kube_config(config_file=None,
                     context=None,
                     client_configuration=None,
                     persist_config=True,
                     get_google_credentials=None,
                     print_config=False,
                     **kwargs):
  """Loads authentication and cluster information from kube-config file
  and stores them in kubernetes.client.configuration.

  :param config_file: Name of the kube-config file.
  :param context: set the active context. If is set to None, current_context
      from config file will be used.
  :param client_configuration: The kubernetes.client.ConfigurationObject to
      set configs to.
  :param persist_config: If True, config file will be updated when changed
      (e.g GCP token refresh).
  """

  if config_file is None:
    config_file = os.path.expanduser(kube_config.KUBE_CONFIG_DEFAULT_LOCATION)
  logging.info("Using Kubernetes config file: %s", config_file)

  config_persister = None
  if persist_config:

    def _save_kube_config(config_map):
      with open(config_file, 'w') as f:
        yaml.safe_dump(config_map, f, default_flow_style=False)

    config_persister = _save_kube_config

  loader = kube_config._get_kube_config_loader_for_yaml_file(  # pylint: disable=protected-access
    config_file,
    active_context=context,
    config_persister=config_persister,
    get_google_credentials=get_google_credentials,
    **kwargs)

  if client_configuration is None:
    config = type.__call__(kubernetes_configuration.Configuration)
    loader.load_and_set(config) # pylint: disable=too-many-function-args
    kubernetes_configuration.Configuration.set_default(config)
  else:
    loader.load_and_set(client_configuration) # pylint: disable=too-many-function-args
  # Dump the loaded config.

  # Warning this will print out any access tokens stored in your kubeconfig
  if print_config:
    run(["kubectl", "config", "view"])


def aws_configure_credential():
  if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
    logging.info("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set;")
  else:
    logging.info("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are not set.")
  run([
    "aws", "eks", "update-kubeconfig", "--name=" + os.getenv("AWS_EKS_CLUSTER")
  ])


def filter_spartakus(spec):
  """Remove spartakus from the list of applications in KfDef."""
  for i, app in enumerate(spec["applications"]):
    if app["name"] == "spartakus":
      spec["applications"].pop(i)
      break
  return spec


def upload_to_s3(contents, target, file_name):
  """Uploading contents to s3"""
  s3 = boto3.resource('s3')
  bucket_name, path = split_s3_uri(target)
  with open(file_name, "w+") as data:
    data.write(contents)
  logging.info("Uploading file %s to %s.", file_name, target)
  s3.meta.client.upload_file(file_name, bucket_name, path)


def upload_file_to_s3(source, target):
  s3 = boto3.resource('s3')
  bucket_name, path = split_s3_uri(target)
  logging.info("Uploading file %s to %s.", source, target)
  s3.meta.client.upload_file(source, bucket_name, path)


def makedirs(path):
  """
  makedirs creates a directory if it doesn't already exist
  :param path: name of the directory
  :return: No return value
  """
  try:
    os.makedirs(path)
  except OSError as e:
    if 'File exists' not in str(e):
      raise


class JobTimeoutError(TimeoutError):
  """An error indicating the job timed out.
  The job spec/status can be found in .job.
  """

  def __init__(self, message, job):
    super(JobTimeoutError, self).__init__(message)
    self.job = job


def set_pytest_junit(record_xml_attribute, test_name, test_target_name=""):
  """Set various xml attributes in the junit produced by pytest.

  pytest supports setting various XML attributes in the junit file.
  http://doc.pytest.org/en/latest/usage.html#record-xml-attribute

  test grid supports grouping based on these attributes
  https://github.com/kubernetes/test-infra/tree/master/testgrid#grouping-tests

  The goal of this function is to set these attributes in a consistent fashion
  to allow easy grouping of tests that were run as part of the same workflow.
  """
  # Look for an environment variable named test target name if not given.
  if not test_target_name:
    TARGET_ENV_NAME = "TEST_TARGET_NAME"
    test_target_name = os.getenv(TARGET_ENV_NAME)

  full_test_name = test_name
  if test_target_name:
    # Override the classname attribute in the junit file.
    # This makes it easy to group related tests in test grid.
    # http://doc.pytest.org/en/latest/usage.html#record-xml-attribute
    # Its currently unclear whether testgrid uses classname or testsuite
    # Based on the code it looks like its using testsuite name but it
    # it doesn't look like we can set that using pytest
    record_xml_attribute("classname", test_target_name)

    # Test grid supports grouping into a hierarchy based on the test name.
    # To support that we set the test name to include target name.
    full_test_name = "/" + "/".join([test_target_name, test_name])
  else:
    logging.info("Environment variable %s not set; no target name set.",
                 TARGET_ENV_NAME)

  record_xml_attribute("name", full_test_name)


def is_in_cluster():
  """Check if we are running in cluster."""
  # Use the existince of a KSA token to determine if we are in the cluster
  return os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount")