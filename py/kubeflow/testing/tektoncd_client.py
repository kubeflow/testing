"""Some utility functions for working with TfJobs."""

import os
import datetime
import httplib2
import json
import logging
import six
import time

from kubernetes import client as k8s_client
from kubernetes.client import rest
from retrying import retry

from kubeflow.testing import util

GROUP = "tekton.dev"
VERSION = "v1alpha1"
PLURAL = "pipelines"
KIND = "Pipeline"


def log_status(pipeline):
    """A callback to use with wait_for_pipeline."""
    try:
        logging.info("Pipeline %s in namespace %s; phase=%s",
                     pipeline["metadata"]["name"],
                     pipeline["metadata"]["namespace"],
                     pipeline["status"]["phase"])
    except KeyError as e:
        # Ignore the error and just log the stacktrace
        # as sometimes the pipeline object does not have all the fields
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
        if code in [httplib2.UNAUTHORIZED, httplib2.FORBIDDEN, httplib2.GATEWAY_TIMEOUT]:
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
       stop_max_delay=5 * 60 * 1000,
       retry_on_exception=handle_retriable_exception)
def get_namespaced_custom_object_with_retries(namespace, name):
    """Call get_namespaced_customer_object API with retries.

  Args:
    namespace: namespace for the pipeline.
    name: name of the pipeline.
  """
    # Due to https://github.com/kubernetes-client/python-base/issues/59,
    # we need to recreate the API client since it may contain stale auth
    # tokens.
    # TODO(richardsliu): Remove this workaround when the k8s client issue
    # is resolved.
    client = k8s_client.ApiClient()
    crd_api = k8s_client.CustomObjectsApi(client)
    return crd_api.get_namespaced_custom_object(
        GROUP, VERSION, namespace, PLURAL, name)


def wait_for_pipelines(namespace,
                       pipeline_names,
                       timeout=datetime.timedelta(minutes=30),
                       polling_interval=datetime.timedelta(seconds=30),
                       status_callback=None):
    """Wait for multiple pipelines to finish.

  Args:
    namespace: namespace for the pipeline.
    pipeline_names: Names of the pipelines to wait for.
    timeout: How long to wait for the pipeline.
    polling_interval: How often to poll for the status of the pipeline.
    status_callback: (Optional): Callable. If supplied this callable is
      invoked after we poll the job. Callable takes a single argument which
      is the job.

  Returns:
    results: A list of the final status of the pipelines.
  Raises:
    ExceptionWithPipelineResults: A custom exception that wraps the internal
    exceptions and stores the most recent set of pipeline results.
  """
    end_time = datetime.datetime.now() + timeout
    while True:
        all_results = []

        try:
            for name in pipeline_names:
                results = get_namespaced_custom_object_with_retries(namespace, name)
                all_results.append(results)
                if status_callback:
                    status_callback(results)
        except Exception as e:
            raise util.ExceptionWithPipelineResults(repr(e), all_results)

        done = True
        for results in all_results:
            # Sometimes it takes a while for the argo controller to populate
            # the status field of an object.
            if results.get("status", {}).get("phase", "") not in ["Failed", "Succeeded"]:
                done = False
                break

        if done:
            return all_results

        if datetime.datetime.now() + polling_interval > end_time:
            message = "Timeout waiting for pipelines {0} in namespace {1} " \
                      "to finish".format(",".join(pipeline_names), namespace)
            raise util.ExceptionWithPipelineResults(message, all_results)

        time.sleep(polling_interval.seconds)


def wait_for_pipeline(namespace, name,
                      timeout=datetime.timedelta(minutes=30),
                      polling_interval=datetime.timedelta(seconds=30),
                      status_callback=None):
    """Wait for the specified pipeline to finish.

  Args:
    namespace: namespace for the pipeline.
    name: Name of the pipeline
    timeout: How long to wait for the pipeline.
    polling_interval: How often to poll for the status of the pipeline.
    status_callback: (Optional): Callable. If supplied this callable is
      invoked after we poll the job. Callable takes a single argument which
      is the job.

  Raises:
    TimeoutError: If timeout waiting for the job to finish.
  """
    results = wait_for_pipelines(namespace, [name],
                                 timeout, polling_interval, status_callback)
    return results[0]


class PipelineRun:
    def __init__(self, function):
        self.function = function
        self.command = "/usr/local/bin/kfctl"
        self.app_dir = ""
        self.args = []
        self.config = ""
        self.cwd = os.getenv("HOME")
        self.env = {}
        self.tests = []

    def __call__(self, **kwargs):
        result = self.function(self, **kwargs)
        return result

    def parse_args(self, **kwargs):
        env = kwargs.pop("env", {})
        self.env = {env[i].split("=")[0]: env[i].split("=")[1] for i in range(0, len(env))}
        if "config" in kwargs:
            self.config += "--config " + kwargs["config"]
            self.args.extend([self.config])
        if "app_dir" in kwargs:
            self.app_dir = kwargs["app_dir"]
            self.cwd = os.path.join(self.app_dir, os.pardir)
            self.args.extend([self.app_dir])
        if "tests" in kwargs:
            self.tests = kwargs["tests"]

    def wait(self):
        return NotImplemented

    def finish(self):
        return True


# adding decorator to the PipelineRun class
@PipelineRun
def run_pipeline(self, **kwargs):
    self.parse_args(**kwargs)
    # kfctl init
    args = [self.command, "init"]
    args.extend([self.config, self.app_dir])
    command = " ".join(args)
    util.run(command, cwd=self.cwd, env=self.env)
    # kfctl generate k8s
    args = [self.command, "generate", "k8s"]
    args.extend([self.email, self.zone])
    command = " ".join(args)
    util.run(command, cwd=self.app_dir, env=self.env)
    # kfctl apply k8s
    args = [self.command, "apply", "k8s"]
    command = " ".join(args)
    util.run(command, cwd=self.app_dir, env=self.env)
    return
