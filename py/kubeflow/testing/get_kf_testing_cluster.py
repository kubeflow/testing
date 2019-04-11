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
import subprocess
import yaml

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

def list_deployments(project, name_prefix, testing_label, http=None, desc_ordered=True):
  """List all the deployments matching name prefix and having testing labels.

  Args:
    project: string, Name of the deployed project.
    name_prefix: string, Base name of deployments.
    testing_label: string, labels assigned to testing clusters used for identification.
    http: httplib2.Http, An instance of httplib2.Http or something that acts
      like it that HTTP requests will be made through. Should only be used in tests.

  Returns:
    deployments: list of dictionary in the format of {
      "name": string of deployment name,
      "endpoint": string of endpoint service name,
      "insertTime": timestamp deployment is inserted.
      "zone": location of deployment.
    }
  """
  dm = None
  if http:
    # This should only be used in testing.
    dm = discovery.build("deploymentmanager", "v2", http=http)
  else:
    credentials = GoogleCredentials.get_application_default()
    dm = discovery.build("deploymentmanager", "v2", credentials=credentials)
  dm_client = dm.deployments()
  resource_client = dm.resources()

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
      resource = resource_client.get(project=project, deployment=name, resource=name).execute()
      # Skip the latest deployment if having any kind of errors.
      if (resource.get("error", None) and resource.get("error", {}).get("errors", [])) or \
      not resource.get("properties", ""):
        continue
      info = yaml.load(resource.get("properties", ""))
      # Skip deployment without zone info - most likely an error case.
      if not info.get("zone", ""):
        continue
      cls.append({
          "name": name,
          "endpoint": get_deployment_endpoint(project, name),
          "insertTime": d.get("insertTime", "1969-12-31T23:59:59+00:00"),
          "zone": info["zone"],
      })

    if next_page_token is None:
      break
    deployments = dm_client.list(project=project, pageToken=next_page_token,
                                 filter=list_filter).execute()

  return sorted(cls, key=lambda entry: entry["insertTime"],
                reverse=desc_ordered)


def get_deployment(project, name_prefix, testing_label, http=None, desc_ordered=True,
                   field="endpoint"):
  """Retrieve either the latest or the oldest deployed testing cluster.

  Args:
    project: string, Name of the deployed project.
    name_prefix: string, Base name of deployments.
    testing_label: string, Label used to identify testing clusters.
    desc_ordered: bool. Option to either choose the latest or the oldest
      deployment.
    http: httplib2.Http, An instance of httplib2.Http or something that acts
      like it that HTTP requests will be made through. Should only be used in tests.
    field: string, indicates which field(s) needs to return to user. Optional.

  Returns:
    field == "all": dictionary in the format of {
      "name": string of deployment name,
      "endpoint": string of endpoint service name,
      "insertTime": Timestamp deployment is inserted.
      "zone": location of deployment.
    }
    field == ("endpoint", "zone", "name"): string value of the field specified.
  """
  valid_fields = set(["all", "endpoint", "zone", "name"])
  # Bail out early
  if not field in valid_fields:
    raise LookupError("Invalid field given: {0}, should be one of [{1}]".format(
        field, ", ".join(valid_fields)))

  deployments = list_deployments(project, name_prefix, testing_label, http=http,
                                 desc_ordered=desc_ordered)
  if not deployments:
    raise LookupError("No deployments found...")

  if field == "all":
    return deployments[0]
  else:
    return deployments[0][field]

def get_latest(version, project="kubeflow-ci-deployment", testing_label="kf-test-cluster",
               http=None, field="endpoint"):
  """Convenient function to get the latest deployment's information using just version.

  Args:
    version: string, version of deployed testing clusters to find.
    project: string, Name of deployed GCP project. Optional.
    testing_label: string, annotation used to identify testing clusters. Optional.
    http: httplib2.Http, An instance of httplib2.Http or something that acts
      like it that HTTP requests will be made through. Should only be used in tests.
    field: string, indicates which field(s) needs to return to user. Optional.

  Returns:
    field == "all": dictionary in the format of {
      "name": string of deployment name,
      "endpoint": string of endpoint service name,
      "insertTime": Timestamp deployment is inserted.
      "zone": location of deployment.
    }
    field == ("endpoint", "zone", "name"): string value of the field specified.
  """
  name_prefix = "kf-v" + version
  return get_deployment(project, name_prefix, testing_label, http=http, field=field)

def get_latest_credential(version, project="kubeflow-ci-deployment",
                          testing_label="kf-test-cluster"):
  """Convenient function to get the latest deployment information and use it to get
  credentials from GCP.

  Args:
    version: string, version of deployed testing clusters to find.
    project: string, Name of deployed GCP project. Optional.
    testing_label: string, annotation used to identify testing clusters. Optional.
  """
  dm = get_latest(version, project=project, testing_label=testing_label, field="all")
  subprocess.call(["gcloud", "container", "clusters", "get-credentials", dm["name"],
                   "--project="+project, "--zone="+dm["zone"]])

def list_dms(args):
  logging.info("Calling list deployments.")
  name_prefix = args.base_name + args.version
  return list_deployments(args.project, name_prefix, args.testing_cluster_label,
                          desc_ordered=args.find_latest_deployed)

def get_dm(args):
  logging.info("Calling get deployment.")
  name_prefix = args.base_name + args.version
  return get_deployment(args.project, name_prefix, args.testing_cluster_label,
                        desc_ordered=args.find_latest_deployed)

def get_credential(args):
  logging.info("Calling get_credential - this call needs gcloud client CLI.")
  name_prefix = args.base_name + args.version
  get_latest_credential(args.version)

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

  subparsers = parser.add_subparsers()

  _list = subparsers.add_parser(
      "list", help=("List of all deployments."))
  _list.set_defaults(func=list_dms)

  _get = subparsers.add_parser(
      "get", help=("Get deployment information."))
  _get.set_defaults(func=get_dm)

  _get_cred = subparsers.add_parser(
      "get-credentials", help=("Get deployment credentials."))
  _get_cred.set_defaults(func=get_credential)

  args = parser.parse_args()
  args.func(args)

if __name__ == "__main__":
  main()
