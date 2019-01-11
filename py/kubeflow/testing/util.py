"""Utilities used by our python scripts for building and releasing."""
from __future__ import print_function

import datetime
import logging
import os
import re
import subprocess
import time
import urllib
import yaml

import google.auth
import google.auth.transport
import google.auth.transport.requests
from google.cloud import storage  # pylint: disable=no-name-in-module

from googleapiclient import errors
from kubernetes import client as k8s_client
from kubernetes.config import kube_config
from kubernetes.client import configuration as kubernetes_configuration
from kubernetes.client import rest

# Default name for the repo organization and name.
# This should match the values used in Go imports.
MASTER_REPO_OWNER = "tensorflow"
MASTER_REPO_NAME = "k8s"


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
    for line in iter(process.stdout.readline, ''):
      output.append(line.strip())
      logging.info(line.strip())

    time.sleep(polling_interval.total_seconds())

  process.stdout.flush()
  for line in iter(process.stdout.readline, b''):
    output.append(line.strip())
    logging.info(line.strip())

  if process.returncode != 0:
    raise subprocess.CalledProcessError(
      process.returncode, "cmd: {0} exited with code {1}".format(
        " ".join(command), process.returncode), "\n".join(output))

  return "\n".join(output)


# TODO(jlewi): We should update callers to use run and just delete this function.
def run_and_output(*args, **argv):
  return run(*args, **argv)


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


def to_gcs_uri(bucket, path):
  """Convert bucket and path to a GCS URI."""
  return "gs://" + os.path.join(bucket, path)


def create_cluster(gke, project, zone, cluster_request):
  """Create the cluster.

  Args:
    gke: Client for GKE.
    project: The project to create the cluster in
    zone: The zone to create the cluster in.
    cluster_rquest: The request for the cluster.
  """
  request = gke.projects().zones().clusters().create(
    body=cluster_request, projectId=project, zone=zone)

  try:
    logging.info("Creating cluster; project=%s, zone=%s, name=%s", project,
                 zone, cluster_request["cluster"]["name"])
    response = request.execute()
    logging.info("Response %s", response)
    create_op = wait_for_operation(gke, project, zone, response["name"])
    logging.info("Cluster creation done.\n %s", create_op)

  except errors.HttpError as e:
    logging.exception("Exception occured creating cluster: %s, status: %s", e,
                      e.resp["status"])
    # Status appears to be a string.
    if e.resp["status"] == '409':
      pass
    else:
      raise


def delete_cluster(gke, name, project, zone):
  """Delete the cluster.

  Args:
    gke: Client for GKE.
    name: Name of the cluster.
    project: Project that owns the cluster.
    zone: Zone where the cluster is running.
  """

  request = gke.projects().zones().clusters().delete(
    clusterId=name, projectId=project, zone=zone)

  try:
    response = request.execute()
    logging.info("Response %s", response)
    delete_op = wait_for_operation(gke, project, zone, response["name"])
    logging.info("Cluster deletion done.\n %s", delete_op)

  except errors.HttpError as e:
    logging.exception("Exception occured deleting cluster: %s, status: %s", e,
                      e.resp["status"])


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


def configure_kubectl(project, zone, cluster_name):
  logging.info("Configuring kubectl")
  run([
    "gcloud", "--project=" + project, "container", "clusters", "--zone=" + zone,
    "get-credentials", cluster_name
  ])


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

  ext_client = k8s_client.ExtensionsV1beta1Api(api_client)

  while datetime.datetime.now() < end_time:
    deploy = ext_client.read_namespaced_deployment(name, namespace)
    if deploy.status.ready_replicas >= replicas:
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


def wait_for_statefulset(api_client, namespace, name):
  """Wait for deployment to be ready.

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

  apps_client = k8s_client.AppsV1beta1Api(api_client)

  while datetime.datetime.now() < end_time:
    stateful = apps_client.read_namespaced_stateful_set(name, namespace)
    if stateful.status.ready_replicas >= 1:
      logging.info("Statefulset %s in namespace %s is ready", name, namespace)
      return stateful
    logging.info("Waiting for Statefulset %s in namespace %s", name, namespace)
    time.sleep(10)

  logging.error("Timeout waiting for statefulset %s in namespace %s to be "
                "ready", name, namespace)
  raise TimeoutError(
    "Timeout waiting for statefulset {0} in namespace {1}".format(
      name, namespace))


def install_gpu_drivers(api_client):
  """Install GPU drivers on the cluster.

  Note: GPU support in K8s is very much Alpha and this code will
  likely change quite frequently.

  Return:
     ds: Daemonset for the GPU installer
  """
  logging.info("Install GPU Drivers.")
  # Fetch the daemonset to install the drivers.
  link = "https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/stable/nvidia-driver-installer/cos/daemonset-preloaded.yaml"  # pylint: disable=line-too-long
  logging.info("Using daemonset file: %s", link)
  f = urllib.urlopen(link)
  daemonset_spec = yaml.load(f)
  ext_client = k8s_client.ExtensionsV1beta1Api(api_client)
  try:
    namespace = daemonset_spec["metadata"]["namespace"]
    ext_client.create_namespaced_daemon_set(namespace, daemonset_spec)
  except rest.ApiException as e:
    # Status appears to be a string.
    if e.status == 409:
      logging.info("GPU driver daemon set has already been installed")
    else:
      raise


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


def cluster_has_gpu_nodes(api_client):
  """Return true if the cluster has nodes with GPUs."""
  api = k8s_client.CoreV1Api(api_client)
  nodes = api.list_node()

  for n in nodes.items:
    if "cloud.google.com/gke-accelerator" in n.metadata.labels:
      return True
  return False


def setup_cluster(api_client):
  """Setup a cluster.

  This function assumes kubectl has already been configured to talk to your
  cluster.

  Args:
    use_gpus
  """
  use_gpus = cluster_has_gpu_nodes(api_client)
  if use_gpus:
    logging.info("GPUs detected in cluster.")
  else:
    logging.info("No GPUs detected in cluster.")

  if use_gpus:
    install_gpu_drivers(api_client)
  if use_gpus:
    wait_for_gpu_driver_install(api_client)


# TODO(jlewi): TimeoutError should be built in in python3 so once
# we migrate to Python3 we should be able to get rid of this.
class TimeoutError(Exception):  # pylint: disable=redefined-builtin
  """An error indicating an operation timed out."""


GCS_REGEX = re.compile("gs://([^/]*)(/.*)?")


def split_gcs_uri(gcs_uri):
  """Split a GCS URI into bucket and path."""
  m = GCS_REGEX.match(gcs_uri)
  bucket = m.group(1)
  path = ""
  if m.group(2):
    path = m.group(2).lstrip("/")
  return bucket, path


def _refresh_credentials():
  # userinfo.email scope was insufficient for authorizing requests to K8s.
  # We need userinfo.email because role bindings can be expressed in terms
  # of email and these won't work without email scope.
  credentials, _ = google.auth.default(scopes=[
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email"
  ])
  request = google.auth.transport.requests.Request()
  credentials.refresh(request)
  return credentials


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
                     get_google_credentials=_refresh_credentials,
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
  run(["kubectl", "config", "view"])


def maybe_activate_service_account():
  if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    logging.info("GOOGLE_APPLICATION_CREDENTIALS is set; configuring gcloud "
                 "to use service account.")
    run([
      "gcloud", "auth", "activate-service-account",
      "--key-file=" + os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    ])
  else:
    logging.info("GOOGLE_APPLICATION_CREDENTIALS is not set.")


def upload_to_gcs(contents, target):
  gcs_client = storage.Client()

  bucket_name, path = split_gcs_uri(target)

  bucket = gcs_client.get_bucket(bucket_name)
  logging.info("Writing %s", target)
  blob = bucket.blob(path)
  blob.upload_from_string(contents)


def upload_file_to_gcs(source, target):
  gcs_client = storage.Client()
  bucket_name, path = split_gcs_uri(target)

  bucket = gcs_client.get_bucket(bucket_name)

  logging.info("Uploading file %s to %s.", source, target)
  blob = bucket.blob(path)
  blob.upload_from_filename(source)


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
