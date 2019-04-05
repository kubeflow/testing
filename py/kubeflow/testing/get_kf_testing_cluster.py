"""TODO(gabrielwen): DO NOT SUBMIT without one-line documentation for get_kf_testing_cluster.

TODO(gabrielwen): DO NOT SUBMIT without a detailed description of get_kf_testing_cluster.
"""

import argparse
import logging

from googleapiclient import discovery
# from google.cloud import storage
# from kubeflow.testing import util
# from retrying import retry
from oauth2client.client import GoogleCredentials

def list_deployments(project, name_prefix):
  credentials = GoogleCredentials.get_application_default()
  container = discovery.build("container", "v1", credentials=credentials)
  cluster_client = container.projects().locations().clusters()

  clusters = cluster_client.list(parent="projects/{0}/locations/-".format(project)).execute()
  for cluster in clusters.get("clusters", []):
    logging.info("cluster name is %s", cluster.get("name", "NOT_FOUND"))

  return [""]

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

  args = parser.parse_args()
  kf_basename = args.base_name + args.version
  logging.info("Cluster base name = %s", kf_basename)
  list_deployments(args.project, kf_basename)

if __name__ == "__main__":
  main()
