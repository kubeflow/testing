"""The reconciler for autodeployments.

The reconciler is responsible for launching K8s jobs to deploy
Kubeflow as needed and garbage collecting old instances
"""
import collections
import datetime
from dateutil import parser as date_parser
import logging
import time

from kubeflow.testing.auto_deploy import util as auto_deploy_util
from kubeflow.testing import gcp_util

class Reconciler:
  def __init__(self, project=None):

    self.project = project
    # This is a map:
    # Kubeflow version -> List of deployments
    self._deployments = None

  def _get_deployments(self, deployments=None):
    """Build a map of all deployments

    Args:
      deployments: (Optional) Iterator over GCP deployments.
    """
    logging.info("Building map of auto deployments")

    self._deployments = collections.defaultdict(lambda: [])
    if not deployments:
      deployments = gcp_util.deployments_iterator(self.project)

    for d in deployments:
      is_auto_deploy = False
      # Use labels to identify auto-deployed instances
      for label_pair in d.get("labels", []):
        if (label_pair["key"] == "purpose" and
            label_pair["value"] == "kf-test-cluster"):
          is_auto_deploy = True
          break

      if not is_auto_deploy:
        logging.info("Skipping deployment %s; its missing the label", d["name"])

      name = auto_deploy_util.AutoDeploymentName.from_deployment_name(d["name"])

      if not name:
        logging.info("Skipping deployment %s; it is not an auto-deployed instance",
                     d["name"])
        continue

      if auto_deploy_util.is_storage_deployment(d["name"]):
        logging.info(f"Skipping deployment {d['name']}; it is storage")
        continue

      logging.info("Deployment %s is auto deployed", d["name"])

      # TODO(jlewi): We should add a label to the deployment to get the branch
      # rather than relying on the name
      manifests_branch = name.version

      create_time = date_parser.parse(d.get("insertTime"))
      deployment = auto_deploy_util.AutoDeployment(manifests_branch=manifests_branch,
                                                   create_time=create_time,
                                                   deployment_name=d["name"])
      self._deployments[deployment.manifests_branch] = (
        self._deployments[deployment.manifests_branch] + [deployment])


  def _reconcile(self):
    pass

  def run(self, period=datetime.timedelta(minutes=5)):
    """Continuously reconcilation."""

    while True:
      self._reconcile()
      logging.info(f"Wait before reconciling; period")
      time.sleep(period.total_seconds())
