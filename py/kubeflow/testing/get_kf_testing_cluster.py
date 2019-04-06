"""TODO(gabrielwen): DO NOT SUBMIT without one-line documentation for get_kf_testing_cluster.

TODO(gabrielwen): DO NOT SUBMIT without a detailed description of get_kf_testing_cluster.
"""

import argparse
import logging
import re

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

def list_deployments(project, name_prefix, testing_label):
  credentials = GoogleCredentials.get_application_default()
  dm = discovery.build("deploymentmanager", "v2", credentials=credentials)
  dm_client = dm.deployments()

  list_filter = "labels.purpose eq " + testing_label
  name_re = re.compile("{0}\-n[0-9]+\Z".format(name_prefix))
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
          "insertTime": d.get("insertTime", "1969-12-31T23:59:59+00:00"),
      })

    if next_page_token is None:
      break
    deployments = dm_client.list(project=project, pageToken=next_page_token,
                                 filter=list_filter).execute()

  return cls


def get_deployment(project, name_prefix, testing_label, desc_ordered=True):
  pass

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

  args = parser.parse_args()
  kf_basename = args.base_name + args.version
  logging.info("Cluster base name = %s", kf_basename)
  clusters = list_deployments(args.project, kf_basename,
                              args.testing_cluster_label)
  logging.info("found clusters = %s", str(clusters))

if __name__ == "__main__":
  main()
