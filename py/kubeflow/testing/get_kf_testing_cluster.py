"""Find the latest/oldest deployed Kubeflow testing cluster.

User could either import this file as module or run it as a script.
Running it with bash:
  - python -m kubeflow.testing.get_kf_testing_cluster --help
  - python -c "from kubeflow.testing import get_kf_testing_cluster; \
    print(get_kf_testing_cluster.get_deployment(\"kubeflow-ci-deployment\", \
    \"kf-vmaster\", \"kf-test-cluster\"))"
"""

import argparse
import datetime
from dateutil import parser as date_parser
import logging
import pprint
import re
import yaml

from googleapiclient import discovery
from kubeflow.testing import util
from oauth2client.client import GoogleCredentials
from retrying import retry

# Default pattern to match auto deployed clusters from master
DEFAULT_PATTERN = r"kf-master-(?!n\d\d)"

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

def list_deployments(project, name_pattern, testing_label, http=None,
                     desc_ordered=True, min_age=datetime.timedelta(minutes=20)):
  """List all the deployments matching name prefix and having testing labels.

  Args:
    project: string, Name of the deployed project.
    name_pattern: string, Regex pattern to match eligible clusters.
    testing_label: string, labels assigned to testing clusters used for identification.
    http: httplib2.Http, An instance of httplib2.Http or something that acts
      like it that HTTP requests will be made through. Should only be used in tests.
    min_age: Minimum age for a deployment to be eligible for inclusion.
      This is a bit of a hack to ensure a Kubeflow deployment is fully
      deployed before we start running samples on it.

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

  list_filter = ""
  if testing_label:
    list_filter = "labels.purpose eq " + testing_label
  # pylint: disable=anomalous-backslash-in-string
  name_re = re.compile(name_pattern)
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

      if name.endswith("storage"):
        continue
      resource = resource_client.get(project=project, deployment=name,
                                     resource=name).execute()

      full_insert_time = d.get("insertTime")

      if not full_insert_time:
        logging.info("Skipping deployment %s; insertion time is unknown",
                     full_insert_time)
        continue
      create_time = date_parser.parse(full_insert_time)
      now = datetime.datetime.now(create_time.tzinfo)

      age = now - create_time

      if age < min_age:
        logging.info("Skipping deployment %s with age %s; it is too new",
                     name, age)
        continue

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
          "insertTime": full_insert_time,
          "zone": info["zone"],
      })

    if next_page_token is None:
      break
    deployments = dm_client.list(project=project, pageToken=next_page_token,
                                 filter=list_filter).execute()

  return sorted(cls, key=lambda entry: entry["insertTime"],
                reverse=desc_ordered)


ZONE_PATTERN = re.compile("([^-]+)-([^-]+)-([^-]+)")

def _iter_cluster(project, location):
  """Iterate over all clusters in the given location"""
  credentials = GoogleCredentials.get_application_default()

  next_page_token = None

  gke = discovery.build("container", "v1", credentials=credentials)

  clusters_client = gke.projects().locations().clusters()

  parent = "projects/{0}/locations/{1}".format(project, location)
  # N.b list doesn't appear to take pagination tokens so hopefully
  # it is handled automatically
  clusters = clusters_client.list(parent=parent).execute()

  for c in clusters.get("clusters", []):
    yield c

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

  return deployments[0][field]

def get_latest(project="kubeflow-ci-deployment", testing_label=None,
               base_name=DEFAULT_PATTERN, http=None, field="endpoint"):
  """Convenient function to get the latest deployment's information using regex.

  Args:
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
  return get_deployment(project, base_name, testing_label, http=http, field=field)

def _get_latest_cluster(project, location, pattern,
                        min_age=datetime.timedelta(minutes=30)):
  """Get the latest cluster matching pattern.

  Args:
   project: The project to search
   location: The location to search (zone or region)
   pattern: The regex to match.
   min_age: Minimum age for a deployment to be eligible for inclusion.
      This is a bit of a hack to ensure a Kubeflow deployment is fully
      deployed before we start running samples on it.
  """

  name_re = re.compile(pattern)

  clusters = []
  for c in _iter_cluster(project, location):
    if not name_re.match(c["name"]):
      continue

    full_insert_time = c.get("createTime")

    if not full_insert_time:
      logging.info("Skipping deployment %s; insertion time is unknown",
                   full_insert_time)
      continue
    create_time = date_parser.parse(full_insert_time)
    now = datetime.datetime.now(create_time.tzinfo)

    age = now - create_time

    if age < min_age:
      logging.info("Skipping cluster %s with age %s; it is too new",
                   c["name"], age)
      continue

    clusters.append(c)

  if not clusters:
    return None

  clusters = sorted(clusters,
                    key=lambda entry: date_parser.parse(entry["createTime"]))

  # most recent cluster will be last
  return clusters[-1]

def get_latest_credential(project="kubeflow-ci-deployment",
                          base_name=DEFAULT_PATTERN,
                          location=None,
                          testing_label=None):
  """Convenient function to get the latest deployment information and use it to get
  credentials from GCP.

  Args:
    project: string, Name of deployed GCP project. Optional.
    location: zone or region to search for clusters.
    testing_label: string, annotation used to identify testing clusters. Optional.
  """
  util.maybe_activate_service_account()

  command = ["gcloud", "container", "clusters", "get-credentials",
              "--project="+project]
  if location:
    c = _get_latest_cluster(project, location, base_name)

    if not c:
      message = ("No clusters found matching: project: {0}, location: {1}, "
                 "pattern: {2}").format(project, location, base_name)
      raise ValueError(message)

    if ZONE_PATTERN.match(location):
      command.append("--zone=" + location)
    else:
      command.append("--region=" + location)
    command.append(c["name"])
  else :
    # This is the pre blueprint which is using deployment manager
    logging.warning("Invoking deprecated path because location not set")
    dm = get_latest(project=project, testing_label=testing_label,
                    base_name=base_name, field="all")
    cluster_name = dm["name"]
    command.append("--zone="+dm["zone"], dm["name"])

  # This call may be flaky due to timeout.
  @retry(stop_max_attempt_number=10, wait_fixed=5000)
  def run_get_credentials():
    util.run(command)
  run_get_credentials()

def list_dms(args):
  logging.info("Calling list deployments.")
  name_prefix = args.base_name
  pp = pprint.PrettyPrinter(indent=1)
  pp.pprint(list_deployments(args.project, name_prefix, args.testing_cluster_label,
                             desc_ordered=args.find_latest_deployed))

def get_dm(args):
  logging.info("Calling get deployment.")
  name_prefix = args.base_name
  pp = pprint.PrettyPrinter(indent=1)
  pp.pprint((get_deployment(args.project, name_prefix, args.testing_cluster_label,
                            field=args.field,
                            desc_ordered=args.find_latest_deployed)))

# TODO(jlewi): It looks like this is just a wrapper intended to parse args.
# Might be simpler just to switch to using Fire and get rid of this indirection.
def get_credential(args):
  logging.info("Calling get_credential - this call needs gcloud client CLI.")
  get_latest_credential(project=args.project, base_name=args.base_name,
                        location=args.location)

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
      "--base_name", default=DEFAULT_PATTERN, type=str,
      help=("Regex to match clusters"))
  parser.add_argument(
      "--testing_cluster_label", default="", type=str,
      help=("Label used to identify the deployment is for testing."))
  parser.add_argument(
      "--field", default="endpoint", type=str,
      choices=["all", "endpoint", "zone", "name"],
      help=("Field of deployment to have."))

  parser.add_argument(
      "--location", default="us-central1", type=str,
      help=("The location to look for clusters."))

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
