from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

def deployments_iterator(project):
  """Iterate over all deployments"""
  credentials = GoogleCredentials.get_application_default()
  dm = discovery.build("deploymentmanager", "v2", credentials=credentials)

  deployments_client = dm.deployments()

  next_page_token = None
  while True:
    deployments = deployments_client.list(project=project,
                                          pageToken=next_page_token,
                                          maxResults=10).execute()

    for d in deployments.get("deployments", []):
      yield d

    if not deployments.get("nextPageToken"):
      return

    next_page_token = deployments.get("nextPageToken")

