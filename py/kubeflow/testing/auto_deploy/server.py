"""A flask app for auto deploying Kubeflow."""

import fire
import logging

from kubeflow.testing import util
from flask import (abort, Flask, session, render_template,
                   session, redirect, url_for, request,
                   flash, jsonify)
from flask_session import Session

app = Flask(__name__)

class AutoDeployServer:

  @staticmethod
  def serve():
    # make sure things reload
    # TODO(jlewi): Should we be
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
    app.run(debug=FLASK_DEBUG, host='0.0.0.0', port=os.getenv('PORT'))

if __name__ == '__main__':
  # Emit logs in json format. This way we can do structured logging
  # and we can query extra fields easily in stackdriver and bigquery.
  json_handler = logging.StreamHandler()
  json_handler.setFormatter(util.CustomisedJSONFormatter())

  logger = logging.getLogger()
  logger.addHandler(json_handler)
  logger.setLevel(logging.INFO)

  fire.Fire(AutoDeployServer)

