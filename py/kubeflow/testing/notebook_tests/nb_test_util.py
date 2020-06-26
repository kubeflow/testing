"""Some utitilies for running notebook tests."""

import datetime
import logging
import os
from urllib.parse import urlencode
import uuid
import yaml

from google.cloud import storage
from kubernetes import client as k8s_client
from kubeflow.testing import util

# This is the bucket where the batch jobs will uploaded an HTML version of the
# notebook will be written to. The K8s job is running in a Kubeflow cluster
# so it needs to be a bucket that the kubeflow cluster can write to.
# This is why we don't write directly to the bucket used for prow artifacts
NB_BUCKET = "kubeflow-ci-deployment"
PROJECT = "kubeflow-ci-deployment"

def logs_for_job(project, job_name):
  """Get a stack driver link for the job with the specified name."""
  logs_filter = f"""resource.type="k8s_container"
labels."k8s-pod/job-name" = "{job_name}"
"""

  new_params = {"project": project,
                # Logs for last 7 days
                "interval": 'P7D',
                "advancedFilter": logs_filter}

  query = urlencode(new_params)

  url = "https://console.cloud.google.com/logs/viewer?" + query

  return url

def run_papermill_job(notebook_path, name, namespace, # pylint: disable=too-many-branches,too-many-statements
                      image, output=""):
  """Generate a K8s job to run a notebook using papermill

  Args:
    notebook_path: Path to the notebook.
    name: Name for the K8s job
    namespace: The namespace where the job should run.
    image: The docker image to run the notebook in.
    output = Location where artifacts like the rendered notebook
      should be uploaded. Should generally be an object storage path.
      Currently only GCS is supported.
  """

  util.maybe_activate_service_account()

  with open("job.yaml") as hf:
    job = yaml.load(hf)

  job["spec"]["template"]["spec"]["containers"][0]["image"] = image

  job["spec"]["template"]["spec"]["containers"][0]["command"] = [
    "python3", "-m",
    "kubeflow.testing.notebook_tests.execute_notebook",
    "--notebook_path", notebook_path]

  job["spec"]["template"]["spec"]["containers"][0]["env"] = [
    {"name": "OUTPUT_GCS", "value": output},
    {"name": "PYTHONPATH",
     "value": "/src/kubeflow/testing/py"},
  ]

  logging.info("Notebook will be written to %s", output)
  util.load_kube_config(persist_config=False)

  if name:
    job["metadata"]["name"] = name
  else:
    job["metadata"]["name"] = ("notebook-test-" +
                               datetime.datetime.now().strftime("%H%M%S")
                               + "-" + uuid.uuid4().hex[0:3])
  name = job["metadata"]["name"]

  job["metadata"]["namespace"] = namespace

  # Create an API client object to talk to the K8s master.
  api_client = k8s_client.ApiClient()
  batch_api = k8s_client.BatchV1Api(api_client)

  logging.info("Creating job:\n%s", yaml.dump(job))
  actual_job = batch_api.create_namespaced_job(job["metadata"]["namespace"],
                                               job)
  logging.info("Created job %s.%s:\n%s", namespace, name,
               yaml.safe_dump(actual_job.to_dict()))

  logging.info("*********************Job logs************************")
  logging.info(logs_for_job(PROJECT, name))
  logging.info("*****************************************************")
  final_job = util.wait_for_job(api_client, namespace, name,
                                timeout=datetime.timedelta(minutes=30))

  logging.info("Final job:\n%s", yaml.safe_dump(final_job.to_dict()))

  logging.info("*********************Job logs************************")
  logging.info(logs_for_job(PROJECT, name))
  logging.info("*****************************************************")

  if not final_job.status.conditions:
    raise RuntimeError("Job {0}.{1}; did not complete".format(namespace, name))

  last_condition = final_job.status.conditions[-1]

  if last_condition.type not in ["Complete"]:
    logging.error("Job didn't complete successfully")
    raise RuntimeError("Job {0}.{1} failed".format(namespace, name))
