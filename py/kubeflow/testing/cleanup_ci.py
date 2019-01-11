"""Cleanup Kubeflow deployments in our ci system."""
import argparse
import datetime
from dateutil import parser as date_parser
import logging
import os
import re
import subprocess
import tempfile

from kubeflow.testing import argo_client
from kubeflow.testing import util
from kubernetes import client as k8s_client
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

# Regexes that select matching deployments
MATCHING = [re.compile("e2e-.*"), re.compile("kfctl.*"),
            re.compile("z-.*"), re.compile(".*presubmit.*")]

def is_match(name):
  for m in MATCHING:
    if m.match(name):
      return True

  return False

def cleanup_workflows(args):
  # We need to load the kube config so that we can have credentials to
  # talk to the APIServer.
  util.load_kube_config(persist_config=False)

  client = k8s_client.ApiClient()
  crd_api = k8s_client.CustomObjectsApi(client)
  workflows = crd_api.list_namespaced_custom_object(
    argo_client.GROUP, argo_client.VERSION, args.namespace, argo_client.PLURAL)

  expired = []
  unexpired = []

  for w in workflows["items"]:
    is_expired = False

    start_time = date_parser.parse(w["status"]["startedAt"])
    now = datetime.datetime.now(start_time.tzinfo)

    name = w["metadata"]["name"]
    age = now - start_time
    if age > datetime.timedelta(hours=args.max_age_hours):
      logging.info("Deleting workflow: %s", name)
      is_expired = True
      crd_api.delete_namespaced_custom_object(
        argo_client.GROUP, argo_client.VERSION, args.namespace,
        argo_client.PLURAL, name, k8s_client.V1DeleteOptions())
      break

    if is_expired:
      expired.append(name)
    else:
      unexpired.append(name)

  logging.info("Unexpired workflows:\n%s", "\n".join(unexpired))
  logging.info("expired workflows:\n%s", "\n".join(expired))

def cleanup_endpoints(args):
  credentials = GoogleCredentials.get_application_default()

  services_management = discovery.build('servicemanagement', 'v1', credentials=credentials)
  services = services_management.services()
  rollouts = services.rollouts()
  next_page_token = None

  expired = []
  unexpired = []
  unmatched = []

  while True:
    results = services.list(producerProjectId=args.project,
                            pageToken=next_page_token).execute()

    for s in results["services"]:
      name = s["serviceName"]
      if not is_match(name):
        unmatched.append(name)
        continue

      all_rollouts = rollouts.list(serviceName=name).execute()
      is_expired = False
      if not all_rollouts.get("rollouts", []):
        logging.info("Service %s has no rollouts", name)
        is_expired = True
      else:
        r = all_rollouts["rollouts"][0]
        create_time = date_parser.parse(r["createTime"])

        now = datetime.datetime.now(create_time.tzinfo)

        age = now - create_time
        if age > datetime.timedelta(hours=args.max_age_hours):
          is_expired = True

      if is_expired:
        logging.info("Deleting service: %s", name)
        is_expired = True
        services.delete(serviceName=name).execute()
        expired.append(name)
      else:
        unexpired.append(name)

    if not "nextPageToken" in results:
      break
    next_page_token = results["nextPageToken"]


  logging.info("Unmatched services:\n%s", "\n".join(unmatched))
  logging.info("Unexpired services:\n%s", "\n".join(unexpired))
  logging.info("expired services:\n%s", "\n".join(expired))

def cleanup_service_accounts(args):
  credentials = GoogleCredentials.get_application_default()

  iam = discovery.build('iam', 'v1', credentials=credentials)
  projects = iam.projects()
  accounts = []
  next_page_token = None
  while True:
    service_accounts = iam.projects().serviceAccounts().list(
           name='projects/' + args.project, pageToken=next_page_token).execute()
    accounts.extend(service_accounts["accounts"])
    if not "nextPageToken" in service_accounts:
      break
    next_page_token = service_accounts["nextPageToken"]

  keys_client = projects.serviceAccounts().keys()

  unmatched_emails = []
  expired_emails = []
  unexpired_emails = []
  # Service accounts don't specify the creation date time. So we
  # use the creation time of the key associated with the account.
  for a in accounts:
    if not is_match(a["email"]):
      logging.info("Skipping key %s; it does not match expected names.",
                   a["email"])

      unmatched_emails.append(a["email"])
      continue

    keys = keys_client.list(name=a["name"]).execute()

    is_expired = False
    for k in keys["keys"]:
      valid_time = date_parser.parse(k["validAfterTime"])
      now = datetime.datetime.now(valid_time.tzinfo)

      age = now - valid_time
      if age > datetime.timedelta(hours=args.max_age_hours):
        logging.info("Deleting account: %s", a["email"])
        iam.projects().serviceAccounts().delete(name=a["name"]).execute()
        is_expired = True
        break

    if is_expired:
      expired_emails.append(a["email"])
    else:
      unexpired_emails.append(a["email"])

  logging.info("Unmatched emails:\n%s", "\n".join(unmatched_emails))
  logging.info("Unexpired emails:\n%s", "\n".join(unexpired_emails))
  logging.info("expired emails:\n%s", "\n".join(expired_emails))

def cleanup_deployments(args): # pylint: disable=too-many-statements
  if not args.delete_script:
    raise ValueError("--delete_script must be specified.")

  credentials = GoogleCredentials.get_application_default()
  dm = discovery.build("deploymentmanager", "v2", credentials=credentials)

  manifests_client = dm.manifests()
  deployments_client = dm.deployments()
  deployments = deployments_client.list(project=args.project).execute()

  for d in deployments.get("deployments", []):
    if not d.get("insertTime", None):
      logging.warning("Deployment %s doesn't have a deployment time "
                      "skipping it", d["name"])
      continue

    name = d["name"]

    if not is_match(name):
      logging.info("Skipping Deployment %s; it does not match expected names.",
                   name)
      continue

    full_insert_time = d.get("insertTime")
    # The docs say insert time will be in RFC339 format.
    # But it looks like it also includes a time zone offset in the form
    # -HH:MM; which is slightly different from what datetime strftime %z
    # uses (no colon).
    # https://cloud.google.com/deployment-manager/docs/reference/latest/deployments/insert
    #
    # So we parse out the hours.
    #
    # TODO(jlewi): Can we use date_parser like we do in cleanup_service_accounts
    insert_time_str = full_insert_time[:-6]
    tz_offset = full_insert_time[-6:]
    hours_offset = int(tz_offset.split(":", 1)[0])
    RFC3339 = "%Y-%m-%dT%H:%M:%S.%f"
    insert_time = datetime.datetime.strptime(insert_time_str, RFC3339)

    # Convert the time to UTC
    insert_time_utc = insert_time + datetime.timedelta(hours=-1 * hours_offset)

    age = datetime.datetime.utcnow()- insert_time_utc

    if age > datetime.timedelta(hours=args.max_age_hours):
      command = [args.delete_script, args.project, name]
      cwd = None
      # If we download the manifests first delete_deployment will issue
      # an update before the delete which can help do a clean delete.
      # But that has the disadvantage of creating GKE clusters if they have
      # already been deleted; which is slow and wasteful.
      if args.update_first:
        # Download the manifest for this deployment.
        # We want to do an update and then a delete because this is necessary
        # for deleting role bindings.
        manifest_url = d["manifest"]
        manifest_name = manifest_url.split("/")[-1]
        manifest = manifests_client.get(
          project=args.project, deployment=name, manifest=manifest_name).execute()

        # Create a temporary directory to store the deployment.
        manifest_dir = tempfile.mkdtemp(prefix="tmp" + name)
        logging.info("Creating directory %s to store manifests for deployment %s",
                     manifest_dir, name)
        with open(os.path.join(manifest_dir, "cluster-kubeflow.yaml"), "w") as hf:
          hf.write(manifest["config"]["content"])

        for i in manifest["imports"]:
          with open(os.path.join(manifest_dir, i["name"]), "w") as hf:
            hf.write(i["content"])

        command.append("cluster-kubeflow.yaml")
        cwd = manifest_dir
      logging.info("Deleting deployment %s; inserted at %s", name,
                   full_insert_time)

      # We could potentially run the deletes in parallel but that would lead
      # to very confusing logs.
      subprocess.check_call(command, cwd=cwd)

  gke = discovery.build("container", "v1", credentials=credentials)

  clusters_client = gke.projects().zones().clusters()

  for zone in args.zones.split(","):
    clusters = clusters_client.list(projectId=args.project, zone=zone).execute()

    for c in clusters["clusters"]:
      name = c["name"]
      if not is_match(name):
        logging.info("Skipping cluster%s; it does not match expected names.",
                     name)
        continue

      full_insert_time = c["createTime"]
      insert_time_str = full_insert_time[:-6]
      tz_offset = full_insert_time[-6:]
      hours_offset = int(tz_offset.split(":", 1)[0])
      RFC3339 = "%Y-%m-%dT%H:%M:%S"
      insert_time = datetime.datetime.strptime(insert_time_str, RFC3339)

      # Convert the time to UTC
      insert_time_utc = insert_time + datetime.timedelta(hours=-1 * hours_offset)
      age = datetime.datetime.utcnow()- insert_time_utc

      if age > datetime.timedelta(hours=args.max_age_hours):
        logging.info("Deleting cluster %s in zone %s", name, zone)

        clusters_client.delete(projectId=args.project, zone=zone,
                               clusterId=name).execute()

def main():
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--project", default="kubeflow-ci", type=str, help=("The project."))

  parser.add_argument(
    "--max_age_hours", default=3, type=int, help=("The age of deployments to gc."))

  subparsers = parser.add_subparsers()

  ######################################################
  # Parser for argo_workflows
  parser_argo = subparsers.add_parser(
    "workflows", help="Cleanup workflows")

  parser_argo.add_argument(
      "--namespace", default="kubeflow-test-infra",
      help="Namespace to cleanup.")

  parser_argo.set_defaults(func=cleanup_workflows)

  ######################################################
  # Parser for endpoints
  parser_endpoints = subparsers.add_parser(
    "endpoints", help="Cleanup endpoints")

  parser_endpoints.set_defaults(func=cleanup_endpoints)

  ######################################################
  # Parser for service accounts
  parser_service_account = subparsers.add_parser(
    "service_accounts", help="Cleanup service accounts")

  parser_service_account.set_defaults(func=cleanup_service_accounts)

  ######################################################
  # Parser for deployments
  parser_deployments = subparsers.add_parser(
    "deployments", help="Cleanup deployments")

  parser_deployments.add_argument(
    "--update_first", default=False, type=bool,
    help="Whether to update the deployment first.")

  parser_deployments.add_argument(
    "--delete_script", default="", type=str,
    help=("The path to the delete_deployment.sh script which is in the "
          "Kubeflow repository."))

  parser_deployments.add_argument(
    "--zones", default="us-east1-d,us-central1-a", type=str,
    help="Comma separated list of zones to check.")

  parser_deployments.set_defaults(func=cleanup_deployments)
  args = parser.parse_args()

  args.func(args)

if __name__ == "__main__":
  main()
