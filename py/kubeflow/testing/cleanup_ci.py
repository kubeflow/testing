"""Cleanup Kubeflow deployments in our ci system."""
import argparse
import datetime
from dateutil import parser as date_parser
import logging
import os
import re
import retrying
import socket
import subprocess
import tempfile
import yaml

from kubeflow.testing import argo_client
from kubeflow.testing import util
from kubernetes import client as k8s_client
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

# Regexes that select matching deployments
MATCHING = [re.compile("e2e-.*"), re.compile("kfctl.*"),
            re.compile("z-.*"), re.compile(".*presubmit.*")]

MATCHING_FIREWALL_RULES = [re.compile("gke-kfctl-.*"),
                           re.compile("gke-e2e-.*"),
                           re.compile(".*presubmit.*"),
                           re.compile(".*postsubmit.*")]

# Regexes that select matching disks
MATCHING_DISK = [re.compile(".*postsubmit.*"), re.compile(".*presubmit.*")]

def is_match_disk(name):
  for m in MATCHING_DISK:
    if m.match(name):
      return True

  return False

def is_match(name, patterns=None):
  if not patterns:
    patterns = MATCHING
  for m in patterns:
    if m.match(name):
      return True

  return False

def is_retryable_exception(exception):
  """Return True if we consider the exception retryable"""
  # Socket errors look like temporary problems connecting to GCP.
  return isinstance(exception, socket.error)

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
      if not args.dryrun:
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
        if not args.dryrun:
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

def cleanup_disks(args):
  credentials = GoogleCredentials.get_application_default()

  compute = discovery.build('compute', 'v1', credentials=credentials)
  disks = compute.disks()
  next_page_token = None

  expired = []
  unexpired = []
  unmatched = []

  for zone in args.zones.split(","):
    while True:
      results = disks.list(project=args.project,
                           zone=zone,
                           pageToken=next_page_token).execute()
      if not "items" in results:
        break
      for d in results["items"]:
        name = d["name"]
        if not is_match_disk(name):
          unmatched.append(name)
          continue

        age = getAge(d["creationTimestamp"])
        if age > datetime.timedelta(hours=args.max_age_hours):
          logging.info("Deleting disk: %s, age = %r", name, age)
          if not args.dryrun:
            response = disks.delete(project=args.project, zone=zone, disk=name)
          logging.info("respone = %s", response)
          expired.append(name)
        else:
          unexpired.append(name)
      if not "nextPageToken" in results:
        break
      next_page_token = results["nextPageToken"]

  logging.info("Unmatched disks:\n%s", "\n".join(unmatched))
  logging.info("Unexpired disks:\n%s", "\n".join(unexpired))
  logging.info("expired disks:\n%s", "\n".join(expired))

def cleanup_firewall_rules(args):
  credentials = GoogleCredentials.get_application_default()

  compute = discovery.build('compute', 'v1', credentials=credentials)
  firewalls = compute.firewalls()
  next_page_token = None

  expired = []
  unexpired = []
  unmatched = []

  while True:
    results = firewalls.list(project=args.project,
                             pageToken=next_page_token).execute()
    if not "items" in results:
      break
    for d in results["items"]:
      name = d["name"]

      match = False
      if is_match(name, patterns=MATCHING_FIREWALL_RULES):
        match = True

      for tag in d.get("targetTags", []):
        if is_match(tag, patterns=MATCHING_FIREWALL_RULES):
          match = True
          break

      if not match:
        unmatched.append(name)
        continue

      age = getAge(d["creationTimestamp"])
      if age > datetime.timedelta(hours=args.max_age_hours):
        logging.info("Deleting firewall: %s, age = %r", name, age)
        if not args.dryrun:
          response = firewalls.delete(project=args.project,
                                      firewall=name).execute()
          logging.info("respone = %s", response)
        expired.append(name)
      else:
        unexpired.append(name)
    if not "nextPageToken" in results:
      break
    next_page_token = results["nextPageToken"]

  logging.info("Unmatched firewall rules:\n%s", "\n".join(unmatched))
  logging.info("Unexpired firewall rules:\n%s", "\n".join(unexpired))
  logging.info("expired firewall rules:\n%s", "\n".join(expired))


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

    is_expired = True
    for k in keys["keys"]:
      valid_time = date_parser.parse(k["validAfterTime"])
      now = datetime.datetime.now(valid_time.tzinfo)

      age = now - valid_time
      if age < datetime.timedelta(hours=args.max_age_hours):
        is_expired = False
        break
    if is_expired:
      logging.info("Deleting account: %s", a["email"])
      if not args.dryrun:
        iam.projects().serviceAccounts().delete(name=a["name"]).execute()
      expired_emails.append(a["email"])
    else:
      unexpired_emails.append(a["email"])

  logging.info("Unmatched emails:\n%s", "\n".join(unmatched_emails))
  logging.info("Unexpired emails:\n%s", "\n".join(unexpired_emails))
  logging.info("expired emails:\n%s", "\n".join(expired_emails))


def trim_unused_bindings(iamPolicy, accounts):
  keepBindings = []
  for binding in iamPolicy['bindings']:
    members_to_keep = []
    members_to_delete = []
    for member in binding['members']:
      if not member.startswith('serviceAccount:'):
        members_to_keep.append(member)
      else:
        accountEmail = member[15:]
        if (not is_match(accountEmail)) or (accountEmail in accounts):
          members_to_keep.append(member)
        else:
          members_to_delete.append(member)
    if members_to_keep:
      binding['members'] = members_to_keep
      keepBindings.append(binding)
    if members_to_delete:
      logging.info("Delete binding for members:\n%s", ", ".join(members_to_delete))
  iamPolicy['bindings'] = keepBindings

def cleanup_service_account_bindings(args):
  credentials = GoogleCredentials.get_application_default()
  iam = discovery.build('iam', 'v1', credentials=credentials)
  accounts = []
  next_page_token = None
  while True:
    service_accounts = iam.projects().serviceAccounts().list(
      name='projects/' + args.project, pageToken=next_page_token).execute()
    for a in service_accounts["accounts"]:
      accounts.append(a["email"])
    if not "nextPageToken" in service_accounts:
      break
    next_page_token = service_accounts["nextPageToken"]

  resourcemanager = discovery.build('cloudresourcemanager', 'v1', credentials=credentials)
  iamPolicy = resourcemanager.projects().getIamPolicy(resource=args.project).execute()
  trim_unused_bindings(iamPolicy, accounts)

  setBody = {'policy': iamPolicy}
  if not args.dryrun:
    resourcemanager.projects().setIamPolicy(resource=args.project, body=setBody).execute()


def getAge(tsInRFC3339):
  # The docs say insert time will be in RFC339 format.
  # But it looks like it also includes a time zone offset in the form
  # -HH:MM; which is slightly different from what datetime strftime %z
  # uses (no colon).
  # https://cloud.google.com/deployment-manager/docs/reference/latest/deployments/insert
  #
  # So we parse out the hours.
  #
  # TODO(jlewi): Can we use date_parser like we do in cleanup_service_accounts
  insert_time_str = tsInRFC3339[:-6]
  tz_offset = tsInRFC3339[-6:]
  hours_offset = int(tz_offset.split(":", 1)[0])
  RFC3339 = "%Y-%m-%dT%H:%M:%S.%f"
  insert_time = datetime.datetime.strptime(insert_time_str, RFC3339)

  # Convert the time to UTC
  insert_time_utc = insert_time + datetime.timedelta(hours=-1 * hours_offset)
  age = datetime.datetime.utcnow()- insert_time_utc
  return age

@retrying.retry(stop_max_attempt=5,
                retry_on_exception=is_retryable_exception)
def execute_rpc(rpc):
  """Execute a Google RPC request with retries."""
  return rpc.execute()

def cleanup_deployments(args): # pylint: disable=too-many-statements,too-many-branches
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
    age = getAge(full_insert_time)

    if age > datetime.timedelta(hours=args.max_age_hours):
      # Get the zone.
      if "update" in d:
        manifest_url = d["update"]["manifest"]
      else:
        manifest_url = d["manifest"]
      manifest_name = manifest_url.split("/")[-1]

      rpc = manifests_client.get(project=args.project,
                                 deployment=name,
                                 manifest=manifest_name)
      try:
        manifest = execute_rpc(rpc)
      except socket.error as e:
        logging.error("socket error prevented getting manifest %s", e)
        # Try to continue with deletion rather than aborting.
        continue

      # Create a temporary directory to store the deployment.
      manifest_dir = tempfile.mkdtemp(prefix="tmp" + name)
      logging.info("Creating directory %s to store manifests for deployment %s",
                   manifest_dir, name)
      with open(os.path.join(manifest_dir, "cluster-kubeflow.yaml"), "w") as hf:
        hf.write(manifest["config"]["content"])

      config = yaml.load(manifest["config"]["content"])

      if not config:
        logging.warning("Skipping deployment %s because it has no config; "
                        "is it already being deleted?", name)
      zone = config["resources"][0]["properties"]["zone"]
      command = [args.delete_script,
                 "--project=" + args.project, "--deployment=" + name,
                 "--zone=" + zone]
      cwd = None
      # If we download the manifests first delete_deployment will issue
      # an update before the delete which can help do a clean delete.
      # But that has the disadvantage of creating GKE clusters if they have
      # already been deleted; which is slow and wasteful.
      if args.update_first:
        # Download the manifest for this deployment.
        # We want to do an update and then a delete because this is necessary
        # for deleting role bindings.
        command.append("cluster-kubeflow.yaml")
        cwd = manifest_dir
      logging.info("Deleting deployment %s; inserted at %s", name,
                   full_insert_time)

      # We could potentially run the deletes in parallel but that would lead
      # to very confusing logs.
      if not args.dryrun:
        subprocess.check_call(command, cwd=cwd)

  gke = discovery.build("container", "v1", credentials=credentials)

  # Collect clusters for which deployment might no longer exist.
  clusters_client = gke.projects().zones().clusters()

  for zone in args.zones.split(","):
    clusters = clusters_client.list(projectId=args.project, zone=zone).execute()

    if not clusters:
      continue
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

        if not args.dryrun:
          clusters_client.delete(projectId=args.project, zone=zone,
                                 clusterId=name).execute()

def cleanup_all(args):
  cleanup_deployments(args)
  cleanup_endpoints(args)
  cleanup_service_accounts(args)
  cleanup_service_account_bindings(args)
  cleanup_workflows(args)
  cleanup_disks(args)
  cleanup_firewall_rules(args)

def add_workflow_args(parser):
  parser.add_argument(
      "--namespace", default="kubeflow-test-infra",
      help="Namespace to cleanup.")

def add_deployments_args(parser):
  parser.add_argument(
    "--update_first", default=False, type=bool,
    help="Whether to update the deployment first.")

  parser.add_argument(
    "--delete_script", default="", type=str,
    help=("The path to the delete_deployment.sh script which is in the "
          "Kubeflow repository."))
  parser.add_argument(
    "--zones", default="us-east1-d,us-central1-a", type=str,
    help="Comma separated list of zones to check.")

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

  parser.add_argument('--dryrun', dest='dryrun', action='store_true')
  parser.add_argument('--no-dryrun', dest='dryrun', action='store_false')
  parser.set_defaults(dryrun=False)

  subparsers = parser.add_subparsers()

  ######################################################
  # Paraser for everything
  parser_all = subparsers.add_parser(
    "all", help="Cleanup everything")

  add_deployments_args(parser_all)
  add_workflow_args(parser_all)

  parser_all.set_defaults(func=cleanup_all)

  ######################################################
  # Parser for argo_workflows
  parser_argo = subparsers.add_parser(
    "workflows", help="Cleanup workflows")

  add_workflow_args(parser_argo)
  parser_argo.set_defaults(func=cleanup_workflows)

  ######################################################
  # Parser for endpoints
  parser_endpoints = subparsers.add_parser(
    "endpoints", help="Cleanup endpoints")

  parser_endpoints.set_defaults(func=cleanup_endpoints)

  ######################################################
  # Parser for firewallrules
  parser_firewall = subparsers.add_parser(
    "firewall", help="Cleanup firewall rules")

  parser_firewall.set_defaults(func=cleanup_firewall_rules)

  ######################################################
  # Parser for service accounts
  parser_service_account = subparsers.add_parser(
    "service_accounts", help="Cleanup service accounts")

  parser_service_account.set_defaults(func=cleanup_service_accounts)

  ######################################################
  # Parser for deployments
  parser_deployments = subparsers.add_parser(
    "deployments", help="Cleanup deployments")

  add_deployments_args(parser_deployments)
  parser_deployments.set_defaults(func=cleanup_deployments)
  args = parser.parse_args()

  util.maybe_activate_service_account()
  args.func(args)

if __name__ == "__main__":
  main()
