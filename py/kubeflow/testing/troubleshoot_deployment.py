"""Script to try to troubleshoot why a deployment failed.

This is a helper script to make it easier to debug why deployments didn't
start in a test.

THIS ISN't WORKING YET.
"""

import fire
import logging
import re

from google.cloud import logging as google_logging

class TroubleShooter:
  @staticmethod
  def debug(cluster, deployment, project="kubeflow-ci-deployment"):
    """Find out why a deployment failed.

    Args:
      deployment_name: Name of the deployment in format "namespace.name"
    """

    client = google_logging.Client()
    #log_name=f"projects/{project}/logs/events"
    #logger = client.logger()

    # Get the kubernetes events for this deployment
    namespace, name = deployment.split(".", 1)



    # Use a stack to recourse down the list of involved objects
    seen = set()
    involved_objects = [name]

    pod_name = None # pylint: disable=unused-variable
    while involved_objects:
      name = involved_objects.pop()
      seen.add(name)

      events_filter = f"""resource.labels.cluster_name="{cluster}"
  logName="projects/{project}/logs/events"
  jsonPayload.involvedObject.name="{name}"
  jsonPayload.involvedObject.namespace="{namespace}"
  """
      # TODO(jlewi): This seems very slow; maybe we need to add a timestamp filter?
      # What if we add a timestamp filter like timestamp>="2020-01-28T18:54:58.453-0800"
      logging.info(f"Getting events for {name}")
      for entry in client.list_entries(projects=[project], filter_=events_filter):
        logging.info(f"Found event {entry.payload.get('message')}")
        if entry.payload.get("reason") == "ScalingReplicaSet":
          m = re.match("Scaled up replica set ([^ ]*) .*",
                       entry.payload.get("message"))
          if not m:
            logging.info("Could not get replica set from message")
            continue
          new_name = m.group(1)

        m = re.match("Created pod: ([^ ]*)", entry.payload.get("message"))
        if m:
          new_name = m.group(1)
          pod_name = new_name

        if not new_name in seen:
          involved_objects.insert(0, new_name)

    # TODO(jlewi): Fetch container logs. if the container started

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(TroubleShooter)
