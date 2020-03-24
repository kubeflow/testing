"""Utility function to wait for Tekton Pipelineruns.
"""

import logging
import json
import six
import datetime
import os
import time
import uuid
import yaml

if six.PY3:
  import http
else:
  import httplib

from multiprocessing import Pool

from kubernetes import client as k8s_client # pylint: disable=wrong-import-position
from kubernetes.client import rest # pylint: disable=wrong-import-position
from retrying import retry # pylint: disable=wrong-import-position

from kubeflow.testing import util # pylint: disable=wrong-import-position

GROUP = "tekton.dev"
VERSION = "v1alpha1"
PLURAL = "pipelineruns"

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
  return result

def retry_if_not_ended(result):
  if not result.get("status", {}).get("conditions", []):
    return False
  reason = result["status"]["conditions"][0].get("reason", "")
  return not result["status"]["conditions"][0].get("reason", "") in ("Failed", "Succeeded")

@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000,
       stop_max_delay=30*60*1000,
       retry_on_result=retry_if_not_ended)
def get_result(args):
  return get_namespaced_custom_object_with_retries(*args)

def wait_for_workflows(namespace, names):
  if not len(names):
    logging.info("Skipped waiting for Tekton pipelines; no pipeline found.")
    return []

  logging.info("Waiting for Tekton PipelineRun: %s",  names)
  p = Pool(len(names))
  args_list = []
  for n in names:
    args_list.append((namespace, n))
  return p.map(get_result, args_list)

def teardown(repos_dir, namespace, name, params):
  run_path = os.path.join(repos_dir,
                          "kubeflow/testing/tekton/templates/teardown-run.yaml")
  # load pipelinerun
  with open(run_path) as f:
    config = yaml.load(f)

  if config.get("kind", "") != "PipelineRun":
    return []

  # Making PipelineRun name unique.
  name_comps = [config["metadata"]["name"]]
  if os.getenv("REPO_OWNER"):
    name_comps.append(os.getenv("REPO_OWNER"))
  if os.getenv("REPO_NAME"):
    name_comps.append(os.getenv("REPO_NAME"))
  name_comps.append(uuid.uuid4().hex[:10])
  config["metadata"]["name"] = "-".join(name_comps)
  for t in config.get("spec", {}).get("pipelineSpec", {}).get("tasks", []):
    if not "params" in t:
      t["params"] = []
    t["params"].extend(params)

  logging.info("Creating teardown workflow:\n%s", yaml.safe_dump(config))
  # call k8s client to deploy.
  group, version = config["apiVersion"].split("/")
  client = k8s_client.ApiClient()
  crd_api = k8s_client.CustomObjectsApi(client)
  result = crd_api.create_namespaced_custom_object(
      group=group,
      version=version,
      namespace=namespace,
      plural=PLURAL,
      body=config)
  logging.info("Created workflow:\n%s", yaml.safe_dump(result))
  return get_namespaced_custom_object_with_retries(namespace, name)

def run_teardown(args):
  return teardown(*args)

def run_tekton_teardown(repos_dir, namespace, tkn_cleanup_args):
  if not len(tkn_cleanup_args):
    logging.info("Skipped teardown process; no pipeline found.")
    return []

  logging.info("Running tekton teardown: %s", [w[0] for w in tkn_cleanup_args])
  p = Pool(len(tkn_cleanup_args))
  args_list = []
  for w in tkn_cleanup_args:
    args_list.append((repos_dir, namespace, w[0], w[1]))
  return p.map(run_teardown, args_list)

class PipelineRunner(object):
  def __init__(self, config_path, namespace, name):
    self.name = name
    self.namespace = namespace

    with open(config_path) as f:
      self.config = yaml.load(f)
      if self.config.get("kind", "") != "PipelineRun":
        raise ValueError("Invalid config (not PipelineRun): " + self.config)

  def run(self):
    # TODO(gabrielwen): Should we create a client per job?
    client = k8s_client.ApiClient()
    crd_api = k8s_client.CustomObjectsApi(client)

    group, version = self.config["apiVersion"].split("/")
    result = crd_api.create_namespaced_custom_object(
        group=group,
        version=version,
        namespace=namespace,
        plural=PLURAL,
        body=self.config)
    logging.info("Creating teardown workflow:\n%s", yaml.safe_dump(result))
    return result

  def wait(self):
    return get_namespaced_custom_object_with_retries(self.namespace, self.name)
