"""A flask app for auto deploying Kubeflow."""

import datetime
from dateutil import parser as date_parser
import fire
import glob
import logging
import multiprocessing
import os
import tempfile
import yaml

from kubeflow.testing import kf_logging
from kubeflow.testing.auto_deploy import reconciler
from kubeflow.testing.auto_deploy import util
import flask

_deployments_dir = None

app =  flask.Flask(__name__)

@app.route("/")
def auto_deploy_status():
  """Return the status of the auto deployments."""

  files = glob.glob(os.path.join(_deployments_dir, "deployments.*"))

  items = []

  if not files:
    logging.info(f"No matching files in {_deployments_dir}")

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
        }
        labels = []
        for label_key, label_value in d["labels"].items():
          labels.append(f"{label_key}={label_value}")
        row["labels"] = ", ".join(labels)
        items.append(row)

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
  return flask.render_template("index.html", title="Kubeflow Auto Deployments",
                               items=items)

class AutoDeployServer:

  def __init__(self):
    self._deployments_queue = None
    self._deployments_dir = None

  def _fetch_deployments(self):
    while True:
      item = self._deployments_queue.get()

      # Write to the deployments to a file in order to make them
      # available to all the flask threads and processes
      suffix = datetime.datetime.now().strftime("%y%m%d-%H%M%S")

      if not os.path.exists(_deployments_dir):
        os.makedirs(_deployments_dir)

      path = os.path.join(_deployments_dir, f"deployments.{suffix}.yaml")

      logging.info(f"Writing deployments to {path}")
      with open(path, "w") as hf:
        yaml.dump(item, hf)

  def serve(self, config_path, job_template_path, template_folder,
            local_dir=None):
    global _deployments_dir
    global app

    app.template_folder = template_folder
    # make sure things reload
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower()

    # Need to convert it to boolean
    if FLASK_DEBUG in ["true", "t"]:
      FLASK_DEBUG = True
    else:
      FLASK_DEBUG = False

    logging.info(f"FLASK_DEBUG={FLASK_DEBUG}")
    if FLASK_DEBUG:
      app.jinja_env.auto_reload = True
      app.config['TEMPLATES_AUTO_RELOAD'] = True

    if not local_dir:
      local_dir = tempfile.mkdtemp(prefix="auto_deploy")

    _deployments_dir = os.path.join(local_dir, "deployments")

    logging.info(f"Deployments will be written to {self._deployments_dir}")

    # Start the reconciler process
    self._deployments_queue = multiprocessing.Queue()
    logging.info(f"Starting reconciler.")
    auto_reconciler = reconciler.Reconciler.from_config_file(
      config_path, job_template_path, local_dir=local_dir)

    auto_reconciler._queue = self._deployments_queue

    p = multiprocessing.Process(target=auto_reconciler.run)
    p.start()

    reader = multiprocessing.Process(target=self._fetch_deployments)
    reader.start()

    app.run(debug=FLASK_DEBUG, host='0.0.0.0', port=os.getenv('PORT'))

if __name__ == '__main__':
  # Emit logs in json format. This way we can do structured logging
  # and we can query extra fields easily in stackdriver and bigquery.
  json_handler = logging.StreamHandler()
  json_handler.setFormatter(kf_logging.CustomisedJSONFormatter())

  logger = logging.getLogger()
  logger.addHandler(json_handler)
  logger.setLevel(logging.INFO)

  fire.Fire(AutoDeployServer)

