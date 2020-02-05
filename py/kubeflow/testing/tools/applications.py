"""A CLI for updating YAML files defining application CRs.

This tool makes it easier to update and maintain the Application CRs
for each application.
"""

import fire
import logging
import os
import yaml

class AppManager:
  @staticmethod
  def update(version, directory=None):
    """Update the application resources to the specified version.

    Args:
      version: The version to set
      directory: (Optional). Directory to run in defaults to current directory.
    """

    # coerce version to a string
    # This is because versions like "0.2" should be valid
    # but Fire will convert them to a float and when they get dumped to
    # yaml they will be treated as a float which will cause problems
    # with K8s since k8s only allows string labels
    version = str(version)
    if not directory:
      directory = os.getcwd()

    logging.info(f"Looking for application.yaml files in {directory}")

    for base, _, files in os.walk(directory):
      for f in files:
        if f != "application.yaml":
          continue

        path = os.path.join(base, f)

        logging.info(f"Processing {path}")

        with open(path) as hf:
          app = yaml.load(hf)

        labels = app["spec"]["selector"]["matchLabels"]
        app_name = labels.get("app.kubernetes.io/name", "")

        labels["app.kubernetes.io/version"] = version
        labels["app.kubernetes.io/instance"] = (
          f"{app_name}-{version}")

        with open(path, "w") as hf:
          yaml.dump(app, hf)

        # We also need to modify the kustomization file to add the labels
        kustomization_path = os.path.join(base, "kustomization.yaml")

        if not os.path.exists(kustomization_path):
          logging.warning(f"kustomizatin file: {kustomization_path} doesn't "
                          f"exist")

        with open(kustomization_path) as hf:
          kustomize = yaml.load(hf)

        if "commonLabels" not in kustomize:
          kustomize["commonLabels"] = {}

        # Include the version in quotes because we want it to be interpreted
        kustomize["commonLabels"]["app.kubernetes.io/version"] = version
        kustomize["commonLabels"]["app.kubernetes.io/instance"] = (
          f"{app_name}-{version}")

        logging.info(f"Updating {kustomization_path}")

        with open(kustomization_path, "w") as hf:
          yaml.dump(kustomize, hf)

if __name__ == "__main__":

  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(message)s|%(pathname)s|%(lineno)d|'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )

  fire.Fire(AppManager)
