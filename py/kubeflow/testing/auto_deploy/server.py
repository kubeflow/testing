"""A flask app for auto deploying Kubeflow.

TODO(jlewi): Rather than use the multiprocessing package it might
make sense just to run the server and reconciler in separate containers.
They are already communicating through the filesystem so using multi-processing
might just be complicating things. One problem we have right now
is that exceptions in the reconciler aren't propogated to the server.
"""

import datetime
from dateutil import parser as date_parser
import fire
import glob
import logging
import os
import yaml

from kubeflow.testing import gcp_util
from kubeflow.testing import kf_logging
from kubeflow.testing.auto_deploy import blueprint_reconciler
from kubeflow.testing.auto_deploy import util
import flask

_deployments_dir = None

app = flask.Flask(__name__)

_deployments_dir = None

app = flask.Flask(__name__)

def _get_deployments():
  """Return dictionary describing deployment manager deployments."""
  match = os.path.join(_deployments_dir, "deployments.*")
  files = glob.glob(match)

  items = []

  if not files:
    logging.info(f"No matching files for {match}")

  else:
    files = sorted(files)

    latest = files[-1]
    logging.info(f"Reading from {latest}")
    with open(os.path.join(latest)) as hf:
      deployments = yaml.load(hf)

    for v, deployments_list  in deployments.items():
      for d in deployments_list:
        create_time = date_parser.parse(d["create_time"])
        age = datetime.datetime.now(tz=create_time.tzinfo) - create_time
        manifests_commit = d["labels"].get(util.MANIFESTS_COMMIT_LABEL, "")
        row = {
          "pipeline_run": "",
          "pipeline_run_url": "",
          "version": v,
          "deployment_name": d["deployment_name"],
          "creation_time": d.get("create_time", ""),
          "age": f"{age}",
          "manifests_git": manifests_commit,
          "manifests_url": (f"https://github.com/kubeflow/manifests/tree/"
                            f"{manifests_commit}"),
          "kfctl_git": d["labels"].get("kfctl-git", ""),
          "endpoint": f"https://{d['deployment_name']}.endpoints."
          f"kubeflow-ci-deployment.cloud.goog",
          # TODO(jlewi): We are hardcoding the project and zone.
                      "gcloud_command": (f"gcloud --project=kubeflow-ci-deployment "
                             f"container clusters get-credentials "
                             f"--zone={d['zone']} "
                             f"{d['deployment_name']}")
        }
        labels = []
        for label_key, label_value in d["labels"].items():
          labels.append(f"{label_key}={label_value}")
        row["labels"] = ", ".join(labels)
        items.append(row)

  return items

def _get_blueprints():
  """Return dictionary describing blueprints."""
  match = os.path.join(_deployments_dir, "clusters.*")
  files = glob.glob(match)

  items = []

  if not files:
    logging.info(f"No files matched {match}")
    return items

  files = sorted(files)

  latest = files[-1]
  logging.info(f"Reading from {latest}")
  with open(os.path.join(latest)) as hf:
    deployments = yaml.load(hf)

  for _, clusters  in deployments.items():
    for c in clusters:
      create_time = date_parser.parse(c["metadata"]["creationTimestamp"])
      age = datetime.datetime.now(tz=create_time.tzinfo) - create_time
      commit = c["metadata"]["labels"].get(
        blueprint_reconciler.BLUEPRINT_COMMIT_LABEL, "")

      pipeline_run = c["metadata"]["labels"].get("tekton.dev/pipelineRun", "")
      group = c["metadata"]["labels"].get(
        blueprint_reconciler.GROUP_LABEL, blueprint_reconciler.UNKNOWN_GROUP)
      name = c["metadata"]["name"]

      location = c["spec"]["location"]

      location_flag = gcp_util.location_to_type(location)

      row = {
        "version": group,
        "deployment_name": name,
        "creation_time": create_time,
        "age": f"{age}",
        "manifests_git": commit,
        # TODO(jlewi):We shouldn't hardcode the url we should add it
        # as annotation.
        "manifests_url": (f"https://github.com/kubeflow/gcp-blueprints/tree/"
                          f"{commit}"),
        "kfctl_git": "",
        "pipeline_run": pipeline_run,
        # TODO(jlewi): We shouldn't hardcode endpoint.
        "pipline_run_url": (f"https://kf-ci-v1.endpoints.kubeflow-ci.cloud.goog/"
                            f"tekton/#/namespaces/auto-deploy/pipelineruns/"
                            f"{pipeline_run}"),
        # TODO(jlewi): Don't hard code the project
        "endpoint": (f"https://{name}.endpoints."
                     f"kubeflow-ci-deployment.cloud.goog"),
        # TODO(jlewi): We are hardcoding the project and zone.
                    "gcloud_command": (f"gcloud --project=kubeflow-ci-deployment "
                           f"container clusters get-credentials "
                           f"--{location_flag}={location} "
                           f"{name}")
      }
      labels = []
      for label_key, label_value in c["metadata"]["labels"].items():
        labels.append(f"{label_key}={label_value}")
      row["labels"] = ", ".join(labels)
      items.append(row)

  return items

@app.route("/")
def auto_deploy_status():
  """Return the status of the auto deployments."""
  logging.info("Handle auto_deploy_status")
  try:
    logging.info("Get deployments")
    items = _get_deployments()

    logging.info("Get blueprints")
    blueprints = _get_blueprints()

    items.extend(blueprints)

    # Define a key function for the sort.
    # We want to sort by version and age
    def key_func(i):
      # We want unknown version to appear last
      # so we ad a prefix
      if i["version"] == "unknown":
        prefix = "z"
      else:
        prefix = "a"

      return f"{prefix}-{i['version']}-{i['age']}"
    items = sorted(items, key=key_func)

    # Return the HTML
    logging.info("Render template")
    result = flask.render_template("index.html", title="Kubeflow Auto Deployments",
                                   items=items)
  # It looks like when flask debug mode is off the Flask provides unhelpful log
  # messages in the logs. In debug mode the actual exception is returned in
  # the html response.
  except Exception as e:
    logging.error(f"Exception occured: {e}")
    raise
  return result

class AutoDeployServer:

  def __init__(self):
    self._deployments_queue = None
    self._deployments_dir = None

  def serve(self, template_folder, deployments_dir=None, port=None):
    global _deployments_dir # pylint: disable=global-statement
    global app # pylint: disable=global-statement

    app.template_folder = template_folder
    # make sure things reload
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower()

    # Need to convert it to boolean
    if FLASK_DEBUG in ["true", "t"]: # pylint: disable=simplifiable-if-statement
      FLASK_DEBUG = True
    else:
      FLASK_DEBUG = False

    logging.info(f"FLASK_DEBUG={FLASK_DEBUG}")
    if FLASK_DEBUG:
      app.jinja_env.auto_reload = True
      app.config['TEMPLATES_AUTO_RELOAD'] = True

    _deployments_dir = deployments_dir

    logging.info(f"Deployments will be read from {self._deployments_dir}")

    app.run(debug=FLASK_DEBUG, host='0.0.0.0', port=port)

if __name__ == '__main__':
  # Emit logs in json format. This way we can do structured logging
  # and we can query extra fields easily in stackdriver and bigquery.
  json_handler = logging.StreamHandler()
  json_handler.setFormatter(kf_logging.CustomisedJSONFormatter())

  logger = logging.getLogger()
  logger.addHandler(json_handler)
  logger.setLevel(logging.INFO)

  fire.Fire(AutoDeployServer)
