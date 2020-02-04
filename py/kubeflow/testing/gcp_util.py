import logging
import retrying

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

@retrying.retry(stop_max_delay=5*60*1000, wait_exponential_max=10000)
def get_gcp_credentials():
  """Wait for GCP default credentials.

  If we are using workload identity we may need to wait for GCP
  credentials to be available due to networking issues.
  """

  logging.info("Attempting to get GCP default credentials")
  credentials = GoogleCredentials.get_application_default()
  logging.info("Successfully obtain GCP default credentials")
  return credentials

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
