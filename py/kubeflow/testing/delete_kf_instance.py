"""Delete a kubeflow instance."""

import fire
import json
import logging
import retrying

from googleapiclient import discovery
from googleapiclient import errors
from oauth2client.client import GoogleCredentials

from kubeflow.testing import util

@retrying.retry(stop_max_delay=10*60*1000)
def delete_deployment(dm, project, name):
  deployments_client = dm.deployments()
  try:
    op = deployments_client.delete(project=project, deployment=name).execute()
  except errors.HttpError as e:
    if not e.content:
      raise
    error_content = json.loads(e.content)
    message = error_content.get('error', {}).get('message', "")
    logging.info("delete deployment error %s", message)
    code = error_content.get('error', {}).get('code', 0)
    if code == 404: # pylint: disable=no-else-return
      logging.info("Project %s doesn't have deployment %s", project, name)
      return
    elif code == 409:
      logging.info("Conflicting operation in progress")
      raise ValueError("Can't delete deployment confliction operation in "
                       "progress")
    raise
  zone = None
  op = util.wait_for_gcp_operation(dm.operations(), project, zone, op["name"])
  logging.info("Final op: %s", op)

class KFDeleter:
  def delete_kf(self, project, name):
    """Delete a KF instance with the specified name in the specified project."""
    # TODO(jlewi): This is a bit of a hack due to the fact that kfctl
    # doesn't properly handle deletion just given the name of a kubeflow
    # deployment. Once that's fixed we should just use that.
    util.maybe_activate_service_account()

    credentials = GoogleCredentials.get_application_default()
    dm = discovery.build("deploymentmanager", "v2", credentials=credentials)

    for dm_name in [name, name + "-storage"]:
      logging.info("Deleting project %s deployment %s", project, dm_name)
      delete_deployment(dm, project, dm_name)
    # TODO(jlewi): Cleanup other resources like certificates and backends

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                        format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                        )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(KFDeleter)
