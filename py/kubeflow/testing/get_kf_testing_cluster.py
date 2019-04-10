"""Find the latest/oldest deployed Kubeflow testing cluster.

User could either import this file as module or run it as a script.
Running it with bash:
  - python -m kubeflow.testing.get_kf_testing_cluster
  - python -c "from kubeflow.testing import get_kf_testing_cluster; \
    print(get_kf_testing_cluster.get_deployment(\"kubeflow-ci-deployment\", \
    \"kf-vmaster\", \"kf-test-cluster\"))"
"""

import argparse
import logging
import re

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

def get_deployment_endpoint(project, deployment):
  """Format endpoint service name using default logic.

  Args:
    project: str. Name of the deployed project.
    deployment: str. Name of deployment - e.g. app name.

  Returns:
    endpoint_name: str. Endpoint service name.
  """
  return "{deployment}.endpoints.{project}.cloud.goog".format(
      project=project,
      deployment=deployment)

def list_deployments(project, name_prefix, testing_label, http=None):
  """List all the deployments matching name prefix and having testing labels.

  Args:
    project: str. Name of the deployed project.
    name_prefix: str. Base name of deployments.
    testing_label: labels assigned to testing clusters used for identification.

  Returns:
    deployments. list. List of dictionaries with name of deployments,
                 endpoint service name, and the timestamp the deployment is inserted.
  """
  dm = None
  if http:
    # This should only be used in testing.
    dm = discovery.build("deploymentmanager", "v2", http=http)
  else:
    credentials = GoogleCredentials.get_application_default()
    dm = discovery.build("deploymentmanager", "v2", credentials=credentials)
  dm_client = dm.deployments()

  list_filter = "labels.purpose eq " + testing_label
  # pylint: disable=anomalous-backslash-in-string
  name_re = re.compile("{0}\-n[0-9]+\Z".format(name_prefix))
  # pylint: enable=anomalous-backslash-in-string
  deployments = dm_client.list(project=project, filter=list_filter).execute()
  next_page_token = None
  cls = []
  while True:
    next_page_token = deployments.get("nextPageToken", None)
    for d in deployments.get("deployments", []):
      name = d.get("name", "")
      if not name or name_re.match(name) is None:
        continue
      logging.info("deployment name is %s", name)
      logging.info("labels is %s", str(d.get("labels", [])))
      cls.append({
          "name": name,
          "endpoint": get_deployment_endpoint(project, name),
          "insertTime": d.get("insertTime", "1969-12-31T23:59:59+00:00"),
      })

    if next_page_token is None:
      break
    deployments = dm_client.list(project=project, pageToken=next_page_token,
                                 filter=list_filter).execute()

  return cls


def get_deployment(project, name_prefix, testing_label, desc_ordered=True):
  """Retrieve either the latest or the oldest deployed testing cluster.

  Args:
    project: str. Name of the deployed project.
    name_prefix: str. Base name of deployments.
    testing_label: str. Label used to identify testing clusters.
    desc_ordered: bool. Option to either choose the latest or the oldest
                  deployment.

  Returns:
    endpoint_service: str. Name of the endpoint service.
  """
  deployments = list_deployments(project, name_prefix, testing_label)
  if not deployments:
    raise RuntimeError("No deployments found...")
  deployments = sorted(deployments, key=lambda entry: entry["insertTime"],
                       reverse=desc_ordered)
  logging.info("deployments: %s", str(deployments))
  return deployments[0]["endpoint"]

def main(): # pylint: disable=too-many-locals,too-many-statements
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)

  parser = argparse.ArgumentParser()

  parser.add_argument(
      "--project", default="kubeflow-ci-deployment", type=str,
      help=("The project."))
  parser.add_argument(
      "--base_name", default="kf-v", type=str, help=("Deployment name prefix"))
  parser.add_argument(
      "--version", default="master", type=str, choices=["0-5", "master"],
      help=("Kubeflow main version."))
  parser.add_argument(
      "--testing_cluster_label", default="kf-test-cluster", type=str,
      help=("Label used to identify the deployment is for testing."))

  parser.add_argument(
      "--find_latest_deployed", dest="find_latest_deployed",
      action="store_true",
      help=("Looking for the latest deployed testing cluster."))
  parser.add_argument(
      "--find_oldest_deployed", dest="find_latest_deployed",
      action="store_false",
      help=("Looking for the oldest deployed testing cluster."))
  parser.set_defaults(find_latest_deployed=True)

  args = parser.parse_args()
  kf_basename = args.base_name + args.version
  logging.info("Cluster base name = %s", kf_basename)
  logging.info("Looking for the %s deployed cluster...",
               "latest" if args.find_latest_deployed else "oldest")
  logging.info("selected cluster = %s", get_deployment(
      args.project,
      kf_basename,
      args.testing_cluster_label,
      args.find_latest_deployed))

if __name__ == "__main__":
  main()
