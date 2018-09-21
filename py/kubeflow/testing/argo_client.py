"""Some utility functions for working with TfJobs."""

import datetime
import logging
from retrying import retry
import time

from kubernetes import client as k8s_client
from kubernetes.client import rest

from kubeflow.testing import util

GROUP = "argoproj.io"
VERSION = "v1alpha1"
PLURAL = "workflows"
KIND = "Workflow"

def log_status(workflow):
  """A callback to use with wait_for_workflow."""
  try:
    logging.info("Workflow %s in namespace %s; phase=%s",
                 workflow["metadata"]["name"],
                 workflow["metadata"]["namespace"],
                 workflow["status"]["phase"])
  except KeyError as e:
    # Ignore the error and just log the stacktrace
    # as sometimes the workflow object does not have all the fields
    # https://github.com/kubeflow/testing/issues/147
    logging.exception('KeyError: %s', e)


def handle_retriable_exception(exception):
  if isinstance(exception, rest.ApiException) and exception.status == 401:
    # See https://github.com/kubeflow/testing/issues/207.
    # If we get an unauthorized response, just reload the kubeconfig and retry.
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
       stop_max_delay=5*60*1000,
       retry_on_exception=handle_retriable_exception)
def get_namespaced_custom_object_with_retries(namespace, name):
  """Call get_namespaced_customer_object API with retries.

  Args:
    namespace: namespace for the workflow.
    name: name of the workflow.
  """
  client = k8s_client.ApiClient()
  crd_api = k8s_client.CustomObjectsApi(client)
  return crd_api.get_namespaced_custom_object(
    GROUP, VERSION, namespace, PLURAL, name)


def wait_for_workflows(namespace, names,
                      timeout=datetime.timedelta(minutes=30),
                      polling_interval=datetime.timedelta(seconds=30),
                      status_callback=None):
  """Wait for multiple workflows to finish.

  Args:
    namespace: namespace for the workflow.
    names: Names of the workflows to wait for.
    timeout: How long to wait for the workflow.
    polling_interval: How often to poll for the status of the workflow.
    status_callback: (Optional): Callable. If supplied this callable is
      invoked after we poll the job. Callable takes a single argument which
      is the job.

  Returns:
    results: A list of the final status of the workflows.
  Raises:
    TimeoutError: If timeout waiting for the job to finish.
  """
  end_time = datetime.datetime.now() + timeout
  while True:
    all_results = []

    for n in names:
      results = get_namespaced_custom_object_with_retries(namespace, n)
      all_results.append(results)
      if status_callback:
        status_callback(results)

    done = True
    for results in all_results:
      # Sometimes it takes a while for the argo controller to populate
      # the status field of an object.
      if results.get("status", {}).get("phase", "") not in ["Failed", "Succeeded"]:
        done = False

    if done:
      return all_results
    if datetime.datetime.now() + polling_interval > end_time:
      raise util.TimeoutError(
        "Timeout waiting for workflows {0} in namespace {1} to finish.".format(
          ",".join(names), namespace))

    time.sleep(polling_interval.seconds)

  return []

def wait_for_workflow(namespace, name,
                      timeout=datetime.timedelta(minutes=30),
                      polling_interval=datetime.timedelta(seconds=30),
                      status_callback=None):
  """Wait for the specified workflow to finish.

  Args:
    namespace: namespace for the workflow.
    name: Name of the workflow
    timeout: How long to wait for the workflow.
    polling_interval: How often to poll for the status of the workflow.
    status_callback: (Optional): Callable. If supplied this callable is
      invoked after we poll the job. Callable takes a single argument which
      is the job.

  Raises:
    TimeoutError: If timeout waiting for the job to finish.
  """
  results = wait_for_workflows(namespace, [name],
                               timeout, polling_interval, status_callback)
  return results[0]
