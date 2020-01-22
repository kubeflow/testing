"""Script to try to troubleshoot why a deployment failed.

This is a helper script to make it easier to debug why deployments didn't
start in a test.

THIS ISN't WORKING YET.
"""

import fire
from google.cloud import logging

class TroubleShooter:
  @staticmethod
  def debug (cluster, deployment, project="kubeflow-ci-deployment"):
    """Find out why a deployment failed.

    Args:
      deployment_name: Name of the deployment in format "namespace.name"
    """

    client = logging.Client()
    logger = client.logger('log_name')

    # Get the kubernetes events for this deployment
    namespace, name = deployment.split(".", 1)

    events_filter = f"""resource.labels.cluster_name="{cluster}"
logName="projects/{project}/logs/events"
jsonPayload.involvedObject.name="{name}"
"""
    #for entry in logger.list_entries(filter_=events_filter):
    for entry in logger.list_entries(projects=[project]):
      print(entry.payload)

if __name__ == "__main__":
  fire.Fire(TroubleShooter)
