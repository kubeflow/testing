"""Some utility functions for working with TfJobs."""

import datetime
import logging
import time

from kubernetes import client as k8s_client

from kubeflow.testing import util

GROUP = "argoproj.io"
VERSION = "v1alpha1"
PLURAL = "workflows"
KIND = "Workflow"

def log_status(workflow):
  """A callback to use with wait_for_workflow."""
  logging.info("Workflow %s in namespace %s; phase=%s",
           workflow["metadata"]["name"],
           workflow["metadata"]["namespace"],
           workflow["status"]["phase"])

def wait_for_workflows(client, namespace, names,
                      timeout=datetime.timedelta(minutes=30),
                      polling_interval=datetime.timedelta(seconds=30),
                      status_callback=None):
  """Wait for multiple workflows to finish.

  Args:
    client: K8s api client.
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
  crd_api = k8s_client.CustomObjectsApi(client)
  end_time = datetime.datetime.now() + timeout
  while True:
    try:
      all_results = []

      for n in names:
        results = crd_api.get_namespaced_custom_object(
            GROUP, VERSION, namespace, PLURAL, n)

        all_results.append(results)
        if status_callback:
          status_callback(results)

      done = True
      for results in all_results:
        if results["status"]["phase"] not in ["Failed", "Succeeded"]:
          done = False

      if done:
        return all_results
    except Exception as e: # pylint: disable=broad-except
      logging.warning("Caught Exception %s. Ignoring and retrying.", e)
    if datetime.datetime.now() + polling_interval > end_time:
      raise util.TimeoutError(
        "Timeout waiting for workflows {0} in namespace {1} to finish.".format(
          ",".join(names), namespace))

    time.sleep(polling_interval.seconds)

  return []

def wait_for_workflow(client, namespace, name,
                      timeout=datetime.timedelta(minutes=30),
                      polling_interval=datetime.timedelta(seconds=30),
                      status_callback=None):
  """Wait for the specified workflow to finish.

  Args:
    client: K8s api client.
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
  results = wait_for_workflows(client, namespace, [name],
                               timeout, polling_interval, status_callback)
  return results[0]
