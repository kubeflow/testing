"""A flask app for auto deploying Kubeflow."""

import fire
import logging
import multiprocessing
import os

from kubeflow.testing import kf_logging
from kubeflow.testing.auto_deploy import reconciler
import flask
import flask_table

# see https://flask-table.readthedocs.io/en/stable/
# For info about using tables.
class AutoDeployTable(flask_table.Table):
  version = flask_table.Col("Version")
  name = flask_table.Col('Deployment')

app = flask.Flask(__name__)

@app.route("/")
def auto_deploy_status():
  """Return the status of the auto deployments."""

  # Or, equivalently, some dicts
  items = [dict(version='Name1', name='Description1'),
           dict(version='Name2', name='Description2'),
           dict(version='Name3', name='Description3')]

  # Populate the table
  table = AutoDeployTable(items)

  # Return the HTML
  return table.__html__()

class AutoDeployServer:

  @staticmethod
  def serve(config_path, job_template_path, local_dir=None):
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

    # Start the reconciler process

    logging.info(f"Starting reconciler.")
    auto_reconciler = reconciler.Reconciler.from_config_file(
      config_path, job_template_path, local_dir=local_dir)

    p = multiprocessing.Process(target=auto_reconciler.run)
    p.start()
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

