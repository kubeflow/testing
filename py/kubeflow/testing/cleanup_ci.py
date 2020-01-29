"""Cleanup Kubeflow deployments in our ci system."""
# pylint: disable=too-many-lines
import argparse
import collections
import datetime
from dateutil import parser as date_parser
import logging
import re
import retrying
import socket
import sys
import traceback
import time
import yaml

from kubeflow.testing.auto_deploy.util as auto_deploy_util

from kubeflow.testing import argo_client
from kubeflow.testing import util
from kubernetes import client as k8s_client
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

# See https://github.com/kubeflow/testing/issues/444
# We are switching to unique names for auto deployments
# So this matches the new ones.
AUTO_DEPLOY_PATTERNS = [re.compile(r".*kf-vmaster-(?!n\d\d)")]

E2E_PATTERNS = [re.compile(".*e2e-.*"), re.compile(".*kfctl.*"),
                re.compile(".*z-.*"), re.compile(".*presubmit.*"),
                re.compile(".*unittest.*"), re.compile("k8s-ig-.*")]

# Constants enumerating the different classes of infra
# We currently have 2 types
# Deployments created by E2E tests
# Auto deployments from master and release branches
AUTO_INFRA = "auto-deploy"
E2E_INFRA = "e2e"

# We use E2E OWNERLESS for resources that we currently don't know how
# to map back to a particular kubeflow deployment.
# In this case we can't determine whether its an E2E deployment or auto-deployed
# resource. So we we just associae a long max age with this.
E2E_OWNERLESS = "e2e-ownerless"

# Map the different classes of infra to max lifetimes.
MAX_LIFETIME = {
  # Auto infra should live for 8-24 hours to facilitate debugging of examples
  AUTO_INFRA: datetime.timedelta(days=2),
  # E2E infra should be relatively short lived
  E2E_INFRA: datetime.timedelta(hours=3),
  # This should be larger than Auto_infra
  E2E_OWNERLESS: datetime.timedelta(days=2),
}

def name_to_infra_type(name):
  """Given a name map it to the type of infrastructure."""

  if is_match(name, patterns=AUTO_DEPLOY_PATTERNS):
    return AUTO_INFRA

  if is_match(name, patterns=E2E_PATTERNS):
    return E2E_INFRA
  return None

def is_match(name, patterns=None):
  if not patterns:
    patterns = E2E_PATTERNS
  for m in patterns:
    if m.match(name):
      return True

  return False

SERVICE_ACCOUNT = collections.namedtuple("SERVICE_ACCOUNT",
                                         ("name", "project", "suffix"))
def parse_service_account_email(email):
  """Take a string of the form serviceAccount:name@project.suffix

  And returns a tuple with the various pieces
  """
  prefix = "serviceAccount:"

  if not prefix in email:
    return None

  _, just_email = email.split(":", 1)

  name, project_and_suffix = just_email.split("@", 1)

  project, suffix = project_and_suffix.split(".", 1)

  return SERVICE_ACCOUNT(name, project, suffix)

def full_email(service_account):
  """Generate the full email from service account"""
  return "{0}@{1}.{2}".format(service_account.name, service_account.project,
                              service_account.suffix)

def is_retryable_exception(exception):
  """Return True if we consider the exception retryable"""
  # Socket errors look like temporary problems connecting to GCP.
  return isinstance(exception, socket.error)

def cleanup_workflows(args):
  logging.info("Cleanup Argo workflows")
  util.maybe_activate_service_account()

  util.run(["gcloud", "container", "clusters", "get-credentials",
            args.testing_cluster, "--zone=" + args.testing_zone,
            "--project=" + args.testing_project,])

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
    if age > datetime.timedelta(hours=args.max_wf_age_hours):
      logging.info("Deleting workflow: %s", name)
      is_expired = True
      if not args.dryrun:
        try:
          crd_api.delete_namespaced_custom_object(
            argo_client.GROUP, argo_client.VERSION, args.namespace,
            argo_client.PLURAL, name, k8s_client.V1DeleteOptions())
        except Exception as e:  # pylint: disable=broad-except
          logging.error("There was a problem deleting workflow %s.%s; "
                        "error: %s", args.namespace, args.name, e)
    if is_expired:
      expired.append(name)
    else:
      unexpired.append(name)

  logging.info("Unexpired workflows:\n%s", "\n".join(unexpired))
  logging.info("expired workflows:\n%s", "\n".join(expired))
  logging.info("Finished cleanup of Argo workflows")

def cleanup_endpoints(args):
  logging.info("Cleanup Google Cloud Endpoints")
  credentials = GoogleCredentials.get_application_default()

  services_management = discovery.build('servicemanagement', 'v1', credentials=credentials,
                                        cache_discovery=False)
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
      infra_type = name_to_infra_type(name)

      if not infra_type:
        logging.info("Skipping endpoint %s; it does not match any infra type.",
                     name)
        unmatched.append(name)
        continue

      logging.info("Endpoint %s categorized as %s", name, infra_type)

      all_rollouts = rollouts.list(serviceName=name).execute()
      is_expired = False
      max_age = MAX_LIFETIME[infra_type]
      if not all_rollouts.get("rollouts", []):
        logging.info("Service %s has no rollouts", name)
        is_expired = True
      else:
        r = all_rollouts["rollouts"][0]
        create_time = date_parser.parse(r["createTime"])

        now = datetime.datetime.now(create_time.tzinfo)

        age = now - create_time
        if age > max_age:
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
  logging.info("Finished cleanup Google Cloud Endpoints")

def cleanup_disks(args):
  logging.info("Cleanup persistent disks")

  credentials = GoogleCredentials.get_application_default()

  compute = discovery.build('compute', 'v1', credentials=credentials)
  disks = compute.disks()

  expired = []
  unexpired = []
  unmatched = []

  for zone in args.zones.split(","):
    next_page_token = None
    while True:
      results = disks.list(project=args.project,
                           zone=zone,
                           pageToken=next_page_token).execute()
      if not "items" in results:
        break
      for d in results["items"]:
        name = d["name"]

        infra_type = name_to_infra_type(name)

        if not infra_type:
          logging.info("Skipping disk %s; it does not match any infra type.",
                       name)
          unmatched.append(name)
          continue

        logging.info("Disk %s categorized as %s", name, infra_type)

        max_age = MAX_LIFETIME[infra_type]
        age = getAge(d["creationTimestamp"])
        if age > max_age:
          logging.info("Deleting disk: %s, age = %r", name, age)
          if not args.dryrun:
            response = disks.delete(project=args.project, zone=zone,
                                    disk=name).execute()
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
  logging.info("Finished cleanup persistent disks")

def cleanup_firewall_rules(args):
  logging.info("Cleanup firewall rules")

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

      infra_type = name_to_infra_type(name)

      for tag in d.get("targetTags", []):
        tag_infra_type = name_to_infra_type(tag)
        if tag_infra_type:
          infra_type = tag_infra_type

      if not infra_type:
        unmatched.append(name)
        continue

      logging.info("Firewall rule %s classified as infra type %s", name,
                   infra_type)
      max_age = MAX_LIFETIME[infra_type]
      age = getAge(d["creationTimestamp"])
      if age > max_age:
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

def cleanup_instance_groups(args):
  logging.info("Cleanup instance groups")

  if not args.gc_backend_services:
    return
  credentials = GoogleCredentials.get_application_default()
  compute = discovery.build('compute', 'v1', credentials=credentials)
  instanceGroups = compute.instanceGroups()
  next_page_token = None
  deleted = []
  unexpired = []
  in_use = []

  for zone in args.zones.split(","): # pylint: disable=too-many-nested-blocks
    while True:
      results = instanceGroups.list(project=args.project,
                                    zone=zone,
                                    pageToken=next_page_token).execute()
      if not "items" in results:
        break
      for s in results["items"]:
        name = s["name"]
        age = getAge(s["creationTimestamp"])
        size = s["size"]
        if size > 0:
          logging.info("Skipping instance group %s because it is in use by %d "
                       "instances.", name, size)
          in_use.append(name)
          continue

        infra_type = name_to_infra_type(name)
        logging.info("Instance group %s has been identified as %s", name, infra_type)
        if not infra_type:
          logging.info("Instance group %s cannot be identified", name)
          continue
        if age < MAX_LIFETIME[infra_type]:
          logging.info("Instance group %s is not expired under policy for %s", name, infra_type)
          unexpired.append(name)
          continue

        if not args.dryrun:
          try:
            response = instanceGroups.delete(project=args.project,
                                             zone=zone,
                                            instanceGroup=name).execute()
            logging.info("response = %r", response)
            deleted.append(name)
          except Exception as e: # pylint: disable=broad-except
            logging.error(e)
            in_use.append(name)

      if not "nextPageToken" in results:
        break
      next_page_token = results["nextPageToken"]

  logging.info("Unexpired instance groups:\n%s", "\n".join(unexpired))
  logging.info("Deleted instance groups:\n%s", "\n".join(deleted))
  logging.info("In-use instance groups:\n%s", "\n".join(in_use))

def cleanup_url_maps(args):
  if not args.gc_backend_services:
    return

  credentials = GoogleCredentials.get_application_default()
  compute = discovery.build('compute', 'v1', credentials=credentials)
  urlMaps = compute.urlMaps()
  next_page_token = None
  expired = []
  unexpired = []
  in_use = []

  while True:
    results = urlMaps.list(project=args.project,
                           pageToken=next_page_token).execute()
    if not "items" in results:
      break
    for s in results["items"]:
      name = s["name"]
      age = getAge(s["creationTimestamp"])
      if age > MAX_LIFETIME[E2E_OWNERLESS]:
        logging.info("Deleting urlMaps: %s, age = %r", name, age)
        if not args.dryrun:
          try:
            response = urlMaps.delete(project=args.project,
                                      urlMap=name).execute()
            logging.info("response = %r", response)
            expired.append(name)
          except Exception as e: # pylint: disable=broad-except
            logging.error(e)
            in_use.append(name)
      else:
        unexpired.append(name)

    if not "nextPageToken" in results:
      break
    next_page_token = results["nextPageToken"]

  logging.info("Unexpired url maps:\n%s", "\n".join(unexpired))
  logging.info("Deleted expired url maps:\n%s", "\n".join(expired))
  logging.info("Expired but in-use url maps:\n%s", "\n".join(in_use))

def cleanup_target_https_proxies(args):
  if not args.gc_backend_services:
    return

  credentials = GoogleCredentials.get_application_default()
  compute = discovery.build('compute', 'v1', credentials=credentials)
  targetHttpsProxies = compute.targetHttpsProxies()
  next_page_token = None
  expired = []
  unexpired = []
  in_use = []

  delete_ops = []
  while True:
    results = targetHttpsProxies.list(project=args.project,
                                      pageToken=next_page_token).execute()
    if not "items" in results:
      break
    for s in results["items"]:
      name = s["name"]
      age = getAge(s["creationTimestamp"])
      if age > MAX_LIFETIME[E2E_OWNERLESS]:
        logging.info("Deleting urlMaps: %s, age = %r", name, age)
        if not args.dryrun:
          try:
            op = targetHttpsProxies.delete(
              project=args.project, targetHttpsProxy=name).execute()
            delete_ops.append(op)
            expired.append(name)
          except Exception as e: # pylint: disable=broad-except
            logging.error(e)
            in_use.append(name)
      else:
        unexpired.append(name)

    if not "nextPageToken" in results:
      break
    next_page_token = results["nextPageToken"]

  unfinished_ops = wait_ops_max_mins(compute.globalOperations(), args.project,
                                     delete_ops, 20)
  logging.info("Unfinished targetHttpsProxy deletions:\n%s", "\n".join(unfinished_ops))
  logging.info("Unexpired target https proxies:\n%s", "\n".join(unexpired))
  logging.info("Deleted expired target https proxies:\n%s", "\n".join(expired))
  logging.info("Expired but in-use target https proxies:\n%s",
               "\n".join(in_use))

def cleanup_target_http_proxies(args):
  if not args.gc_backend_services:
    return

  credentials = GoogleCredentials.get_application_default()
  compute = discovery.build('compute', 'v1', credentials=credentials)
  targetHttpProxies = compute.targetHttpProxies()
  next_page_token = None
  expired = []
  unexpired = []
  in_use = []

  while True:
    results = targetHttpProxies.list(project=args.project,
                                     pageToken=next_page_token).execute()
    if not "items" in results:
      break
    for s in results["items"]:
      name = s["name"]
      age = getAge(s["creationTimestamp"])
      if age > MAX_LIFETIME[E2E_OWNERLESS]:
        logging.info("Deleting urlMaps: %s, age = %r", name, age)
        if not args.dryrun:
          try:
            response = targetHttpProxies.delete(
              project=args.project, targetHttpProxy=name).execute()
            logging.info("response = %r", response)
            expired.append(name)
          except Exception as e: # pylint: disable=broad-except
            logging.error(e)
            in_use.append(name)
      else:
        unexpired.append(name)

    if not "nextPageToken" in results:
      break
    next_page_token = results["nextPageToken"]

  logging.info("Unexpired target http proxies:\n%s", "\n".join(unexpired))
  logging.info("Deleted expired target http proxies:\n%s", "\n".join(expired))
  logging.info("Expired but in-use target http proxies:\n%s",
               "\n".join(in_use))

def cleanup_forwarding_rules(args):
  if not args.gc_backend_services:
    return

  credentials = GoogleCredentials.get_application_default()
  compute = discovery.build('compute', 'v1', credentials=credentials)
  forwardingRules = compute.globalForwardingRules()
  next_page_token = None
  expired = []
  unexpired = []
  in_use = []

  delete_ops = []
  while True:
    results = forwardingRules.list(project=args.project,
                                   pageToken=next_page_token).execute()
    if not "items" in results:
      break
    for s in results["items"]:
      name = s["name"]
      age = getAge(s["creationTimestamp"])
      if age > MAX_LIFETIME[E2E_OWNERLESS]:
        logging.info("Deleting forwarding rule: %s, age = %r", name, age)
        if not args.dryrun:
          try:
            op = forwardingRules.delete(project=args.project,
                                        forwardingRule=name).execute()
            expired.append(name)
            delete_ops.append(op)
          except Exception as e: # pylint: disable=broad-except
            logging.error(e)
            in_use.append(name)
      else:
        unexpired.append(name)

    if not "nextPageToken" in results:
      break
    next_page_token = results["nextPageToken"]

  unfinished_ops = wait_ops_max_mins(compute.globalOperations(), args.project,
                                     delete_ops, 20)
  logging.info("Unfinished forwarding rule deletions:\n%s", "\n".join(unfinished_ops))
  logging.info("Unexpired forwarding rules:\n%s", "\n".join(unexpired))
  logging.info("Deleted expired forwarding rules:\n%s", "\n".join(expired))
  logging.info("Expired but in-use forwarding rules:\n%s", "\n".join(in_use))

def cleanup_backend_services(args):
  if not args.gc_backend_services:
    return

  credentials = GoogleCredentials.get_application_default()
  compute = discovery.build('compute', 'v1', credentials=credentials)
  backends = compute.backendServices()
  next_page_token = None
  expired = []
  unexpired = []
  in_use = []

  while True:
    results = backends.list(project=args.project,
                            pageToken=next_page_token).execute()
    if not "items" in results:
      break
    for s in results["items"]:
      name = s["name"]
      age = getAge(s["creationTimestamp"])
      if age > MAX_LIFETIME[E2E_OWNERLESS]:
        logging.info("Deleting backend services: %s, age = %r", name, age)
        if not args.dryrun:
          try:
            # An error may be thrown if the backend service is used by a urlMap.
            response = backends.delete(project=args.project,
                                       backendService=name).execute()
            logging.info("response = %r", response)
            expired.append(name)
          except Exception as e: # pylint: disable=broad-except
            logging.error(e)
            in_use.append(name)
      else:
        unexpired.append(name)

    if not "nextPageToken" in results:
      break
    next_page_token = results["nextPageToken"]

  logging.info("Unexpired backend services:\n%s", "\n".join(unexpired))
  logging.info("Deleted backend services:\n%s", "\n".join(expired))
  logging.info("Expired but in-use backend services:\n%s", "\n".join(in_use))


def cleanup_health_checks(args):
  credentials = GoogleCredentials.get_application_default()

  compute = discovery.build('compute', 'v1', credentials=credentials)
  health_checks = compute.healthChecks()
  next_page_token = None

  checks = {}
  while True:
    results = health_checks.list(project=args.project,
                                 pageToken=next_page_token).execute()
    if not "items" in results:
      break
    for d in results["items"]:
      name = d["name"]
      checks[name] = d
    if not "nextPageToken" in results:
      break

    next_page_token = results["nextPageToken"]

  backends = compute.backendServices()
  services = {}
  while True:
    results = backends.list(project=args.project,
                            pageToken=next_page_token).execute()
    if not "items" in results:
      break
    for d in results["items"]:
      name = d["name"]
      services[name] = d

    if not "nextPageToken" in results:
      break

    next_page_token = results["nextPageToken"]

  # Find all health checks not associated with a service.
  unmatched = []
  matched = []
  for name in checks.iterkeys():
    if not name in services:
      unmatched.append(name)
      logging.info("Deleting health check: %s", name)
      if not args.dryrun:
        response = health_checks.delete(project=args.project,
                                        healthCheck=name).execute()
        logging.info("response = %s", response)
    else:
      matched.append(name)


  logging.info("Unmatched health checks:\n%s", "\n".join(unmatched))
  logging.info("Matched health checks:\n%s", "\n".join(matched))
  logging.info("Finished cleanup firewall rules")

def get_ssl_certificate_domain(certificate):
  if "managed" in certificate and "domains" in certificate["managed"]:
    # We use one domain per certificate.
    return certificate["managed"]["domains"][0]

  if "subjectAlternativeNames" in certificate:
    return certificate["subjectAlternativeNames"][0]

  return ""

def cleanup_certificates(args):
  credentials = GoogleCredentials.get_application_default()

  # Using compute beta API other than v1 to get detailed domain information.
  compute = discovery.build('compute', 'beta', credentials=credentials)
  certificates = compute.sslCertificates()
  next_page_token = None

  unexpired = []
  expired = []

  while True:
    results = certificates.list(project=args.project,
                                pageToken=next_page_token).execute()
    if not "items" in results:
      break

    for d in results["items"]:
      create_time = date_parser.parse(d["creationTimestamp"])

      now = datetime.datetime.now(create_time.tzinfo)

      age = now - create_time

      name = d["name"]
      domain = get_ssl_certificate_domain(d)

      infra_type = name_to_infra_type(domain)

      if not infra_type:
        logging.info("Skipping certificate named %s for domain %s; "
                     "it does not match any infra type.", name, domain)
        continue

      logging.info("Certificate named %s for domain %s categorized as %s",
                   name, domain, infra_type)

      if age > MAX_LIFETIME[infra_type]:
        logging.info("Deleting certifcate: %s for domain %s", d["name"], domain)
        is_expired = True
        if not args.dryrun:
          try:
            certificates.delete(
              project=args.project, sslCertificate=d["name"]).execute()
          except Exception as e:  # pylint: disable=broad-except
            logging.error("There was a problem deleting certifcate %s; "
                          "error: %s", d["name"], e)
        if is_expired:
          expired.append("{0} for {1}".format(name, domain))
        else:
          unexpired.append("{0} for {1}".format(name, domain))

    if not "nextPageToken" in results:
      break

    next_page_token = results["nextPageToken"]

  logging.info("Unexpired certificates:\n%s", "\n".join(unexpired))
  logging.info("expired certificates:\n%s", "\n".join(expired))
  logging.info("Finished cleanup certificates")

def cleanup_service_accounts(args):
  logging.info("Cleanup service accounts")

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
    infra_type = name_to_infra_type(a["email"])

    if not infra_type:
      logging.info("Skipping service account %s; it does not match any "
                   "infra type.", a["email"])
      unmatched_emails.append(a["email"])
      continue

    logging.info("Service account %s categorized as %s", a["email"], infra_type)

    keys = keys_client.list(name=a["name"]).execute()

    is_expired = True
    for k in keys["keys"]:
      valid_time = date_parser.parse(k["validAfterTime"])
      now = datetime.datetime.now(valid_time.tzinfo)

      age = now - valid_time
      if age < MAX_LIFETIME[infra_type]:
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
  logging.info("Finished cleanup service accounts")

def trim_unused_bindings(iamPolicy, accounts, project):
  """Trim unused bindings

  Args:
    iamPolicy:The iam policy from which to trim accounts
    accounts: The list of service accounts that still exist
    project: The project that owns the service accounts listed in service
      accounts. Bindings associated with service accounts not owned by
      this project are not eligible for deletion.
  """
  keepBindings = []
  kept_bindings = set()
  deleted_bindings = set()
  for binding in iamPolicy['bindings']:
    members_to_keep = []
    members_to_delete = []
    for member in binding['members']:
      # Parse the binding
      service_account = parse_service_account_email(member)

      if not service_account:
        members_to_keep.append(member)
        kept_bindings.add(member)
        continue

      # Accounts will only be for the service accounts owned by the
      # project. So we can only delete a service account binding if it
      # is associated with a service account that would be owned by
      # that project; otherwise that service account wouldn't be listed
      # in the set of service accounts
      if service_account.project != project:
        members_to_keep.append(member)
        kept_bindings.add(member)
        continue

      if service_account.suffix != "iam.gserviceaccount.com":
        members_to_keep.append(member)
        kept_bindings.add(member)
        continue

      if full_email(service_account) in accounts:
        members_to_keep.append(member)
        kept_bindings.add(member)
        continue

      members_to_delete.append(member)
      deleted_bindings.add(member)

    if members_to_keep:
      binding['members'] = members_to_keep
      keepBindings.append(binding)
    if members_to_delete:
      logging.info("Delete binding for members:\n%s", "\n".join(
        members_to_delete))
  iamPolicy['bindings'] = keepBindings

  logging.info("Removing bindings for following service accounts which "
               "do not exist:\n%s", "\n".join(deleted_bindings))
  logging.info("Keeping bindings for following service accounts which "
               "still exist:\n%s", "\n".join(kept_bindings))

def cleanup_service_account_bindings(args):
  logging.info("Cleanup service account bindings")

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
  logging.info("Get IAM policy for project %s", args.project)
  iamPolicy = resourcemanager.projects().getIamPolicy(resource=args.project, body={}).execute()
  trim_unused_bindings(iamPolicy, accounts, args.project)

  setBody = {'policy': iamPolicy}
  if not args.dryrun:
    resourcemanager.projects().setIamPolicy(resource=args.project, body=setBody).execute()
  else:
    logging.info("Dryrun mode; policy not set; would set to policy;\n%s",
                 yaml.safe_dump(iamPolicy))
  logging.info("Finished cleanup service account bindings")

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

@retrying.retry(stop_max_attempt_number=5,
                retry_on_exception=is_retryable_exception)
def execute_rpc(rpc):
  """Execute a Google RPC request with retries."""
  return rpc.execute()

# Wait for 'ops' to finish in 'max_wait_mins' or return the remaining ops.
# operation_resource must implement 'get()' method.
def wait_ops_max_mins(operation_resource, project, ops, max_wait_mins=15):
  end_time = datetime.datetime.now() + datetime.timedelta(minutes=max_wait_mins)

  while datetime.datetime.now() < end_time and ops:
    not_done = []
    for op in ops:
      op = operation_resource.get(project=project, operation=op["name"]).execute()
      status = op.get("status", "")
      if status != "DONE":
        not_done.append(op)
    ops = not_done
    if ops:
      time.sleep(30)
  return ops

def _iter_deployments(project):
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

def _delete_deployments(project, deployments, max_wait_mins=15):
  """Delete the deployments.

  Args:
   project: The name of the project to delete the deployments in
   deployments: (iterable) names of the deployments to delete
   wait_ops_max_mins: (Optional) max time to wait in minutes
  """
  credentials = GoogleCredentials.get_application_default()
  dm = discovery.build("deploymentmanager", "v2", credentials=credentials)

  deployments_client = dm.deployments()
  delete_ops = []
  for dm_name in deployments:
    try:
      logging.info("Deleting deployment %s in project %s", dm_name,
                   project)
      op = deployments_client.delete(project=project,
                                     deployment=dm_name).execute()
      delete_ops.append(op)
    except Exception as e: # pylint: disable=broad-except
      # Keep going on error because we want to delete the other deployments.
      # TODO(jlewi): Do we need to handle cases by issuing delete with abandon?
      logging.error("There was a problem deleting deployment %s; error %s",
                    dm_name, e)

  delete_ops = wait_ops_max_mins(dm.operations(), project, delete_ops,
                                 max_wait_mins=max_wait_mins)
  not_done_names = [op["name"] for op in delete_ops]

  logging.info("Delete ops that didn't finish:\n%s", "\n".join(not_done_names))


def cleanup_auto_deployments(args, deployments=None): # pylint: disable=too-many-branches
  """Cleanup auto deployed clusters.

  For auto deployments we only want to keep the most recent N deployments.

  Args:
    args: Command line arguments
    deployments: (Optional) iterator over GCP deployment manager deployments.

  Returns:
    dm_to_delete: List of deployments to delete
    dm_to_keep: List of deployments to keep
  """
  logging.info("Cleanup auto deployments")
  # Map from auto-deployed version e.g. "vmaster" to a map of deployment
  # names to their insert time
  auto_deployments = collections.defaultdict(lambda: {})

  if not deployments:
    deployments = _iter_deployments(args.project)

  for d in deployments:
    if not d.get("insertTime", None):
      logging.warning("Deployment %s doesn't have a deployment time "
                      "skipping it", d["name"])
      continue

    is_auto_deploy = False
    # Use labels to identify auto-deployed instances
    for label_pair in d.get("labels", []):
      if (label_pair["key"] == "purpose" and
          label_pair["value"] == "kf-test-cluster"):
        is_auto_deploy = True
        break

    if not is_auto_deploy:
      logging.info("Skipping deployment %s; its missing the label", d["name"])
    name = auto_deploy_util.AutoDeploymentName.from_deployment_name(d["name"])

    if not name:
      logging.info("Skipping deployment %s; it is not an auto-deployed instance",
                   d["name"])
      continue

    logging.info("Deployment %s is auto deployed", d["name"])


    if name.name in auto_deployments[name.version]:
      continue

    auto_deployments[name.version][name.name] = (
      date_parser.parse(d.get("insertTime")))

  # Garbage collect the auto deployments
  to_keep = []
  to_delete = []
  for version, matched_deployments in auto_deployments.items():
    logging.info("For version=%s found deployments:\n%s", version,
                 "\n".join(matched_deployments.keys()))

    # Sort the deployment by the insert time
    pairs = matched_deployments.items()
    sorted_pairs = sorted(pairs, key=lambda x: x[1])

    # keep the 3 most recent deployments
    to_keep.extend([p[0] for p in sorted_pairs[-3:]])
    to_delete.extend([p[0] for p in sorted_pairs[:-3]])

  logging.info("Auto deployments to delete:\n%s", "\n".join(to_delete))
  logging.info("Auto deployments to keep:\n%s", "\n".join(to_keep))

  dm_names = []
  for kf_name in to_delete:
    for dm_name in [kf_name, kf_name + "-storage"]:
      dm_names.append(dm_name)

  if not args.dryrun:
    _delete_deployments(args.project, dm_names)
  else:
    logging.info("Dry run; would delete auto deployments:\n%s",
                 "\n".join(dm_names))

  logging.info("Finish cleanup auto deployments")
  return to_keep, to_delete

def cleanup_deployments(args): # pylint: disable=too-many-statements,too-many-branches
  logging.info("Cleanup deployments")

  deployments = _iter_deployments(args.project)

  unexpired = []
  expired = []

  for d in deployments.get("deployments", []):
    if not d.get("insertTime", None):
      logging.warning("Deployment %s doesn't have a deployment time "
                      "skipping it", d["name"])
      continue

    name = d["name"]

    infra_type = name_to_infra_type(name)

    if not infra_type:
      logging.info("Skipping Deployment %s; it does not match any infra type.",
                   name)
      continue

    logging.info("Deployment %s categorized as %s", name, infra_type)

    full_insert_time = d.get("insertTime")
    age = getAge(full_insert_time)

    if "error" in d.get("operation", {}):
      # Prune failed deployments more aggressively
      logging.info("Deployment %s is in error state %s",
                   d.get("name"), d.get("operation").get("error"))
      max_age = datetime.timedelta(minutes=10)
    else:
      max_age = MAX_LIFETIME[infra_type]

    if age < max_age:
      unexpired.append(name)
      logging.info("Deployment %s has not expired; max age %s", name, max_age)
      continue

    logging.info("Deployment %s has expired; max_age %s", name, max_age)
    expired.append(name)
    logging.info("Deleting deployment %s", name)

  _delete_deployments(args.project, expired)

  logging.info("Unexpired deployments:\n%s", "\n".join(unexpired))
  logging.info("expired deployments:\n%s", "\n".join(expired))
  logging.info("Finished cleanup deployments")

def cleanup_clusters(args):
  logging.info("Cleanup clusters")
  credentials = GoogleCredentials.get_application_default()
  gke = discovery.build("container", "v1", credentials=credentials)

  # Collect clusters for which deployment might no longer exist.
  clusters_client = gke.projects().zones().clusters()

  expired = []
  unexpired = []
  stopping = []

  for zone in args.zones.split(","):
    clusters = clusters_client.list(projectId=args.project, zone=zone).execute()

    if not clusters:
      continue
    for c in clusters["clusters"]:
      name = c["name"]

      infra_type = name_to_infra_type(name)

      if not infra_type:
        logging.info("Skipping cluster %s; it does not match any infra type.",
                     name)
        continue

      logging.info("Deployment %s categorized as %s", name, infra_type)

      full_insert_time = c["createTime"]
      insert_time_str = full_insert_time[:-6]
      tz_offset = full_insert_time[-6:]
      hours_offset = int(tz_offset.split(":", 1)[0])
      RFC3339 = "%Y-%m-%dT%H:%M:%S"
      insert_time = datetime.datetime.strptime(insert_time_str, RFC3339)

      # Convert the time to UTC
      insert_time_utc = insert_time + datetime.timedelta(hours=-1 * hours_offset)
      age = datetime.datetime.utcnow()- insert_time_utc

      # https://cloud.google.com/kubernetes-engine/docs/reference/rest/v1/projects.locations.clusters#Cluster.Status
      if c.get("status", "") in ["ERROR", "DEGRADED"]:
        # Prune failed deployments more aggressively
        logging.info("Cluster %s is in error state; %s", c["name"], c.get("statusMessage", ""))
        max_age = datetime.timedelta(minutes=10)
      else:
        max_age = MAX_LIFETIME[infra_type]

      if age > max_age:
        if c.get("status", "") == "STOPPING":
          logging.info("Cluster %s is already stopping; not redeleting", c["name"])
          stopping.append(c["name"])
          continue
        expired.append(name)
        logging.info("Deleting cluster %s in zone %s", name, zone)

        if not args.dryrun:
          clusters_client.delete(projectId=args.project, zone=zone,
                                 clusterId=name).execute()

      else:
        unexpired.append(name)
  logging.info("Unexpired clusters:\n%s", "\n".join(unexpired))
  logging.info("Already stopping clusters:\n%s", "\n".join(stopping))
  logging.info("expired clusters:\n%s", "\n".join(expired))
  logging.info("Finished cleanup clusters")

# The order of cleanup_forwarding_rules, cleanup_target_http_proxies,
# cleanup_url_maps, cleanup_backend_services, cleanup_instance_groups makes
# sure ingress resources are GCed in one run of this script. See
# https://github.com/kubernetes/ingress-gce/issues/136#issuecomment-371254595

def cleanup_all(args):
  ops = [# Deleting deploymens should be called first because hopefully that will
         # cleanup all the resources associated with the deployment
         cleanup_auto_deployments,
         cleanup_deployments,
         cleanup_clusters,
         cleanup_endpoints,
         cleanup_service_accounts,
         cleanup_service_account_bindings,
         cleanup_workflows,
         cleanup_disks,
         cleanup_forwarding_rules,
         cleanup_target_https_proxies,
         cleanup_target_http_proxies,
         cleanup_certificates,
         cleanup_url_maps,
         cleanup_backend_services,
         cleanup_firewall_rules,
         cleanup_health_checks,
         cleanup_instance_groups]
  for op in ops:
    try:
      op(args)
    except Exception as e: # pylint: disable=broad-except
      logging.error(e)
      exc_type, exc_value, exc_tb = sys.exc_info()
      traceback.print_exception(exc_type, exc_value, exc_tb)

def add_workflow_args(parser):
  parser.add_argument(
    "--namespace", default="kubeflow-test-infra",
      help="Namespace to cleanup.")

def add_deployments_args(parser):
  parser.add_argument(
    "--update_first", default=False, type=bool,
    help="Whether to update the deployment first.")

  # TODO(jlewi): Delete script is no longer used. We only leave it as an argument
  # because some of our cron jobs haven't been updated yet to not use it.
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

  # The values prefixed with testing_ refer to the test cluster where the
  # Argo workflows run. In contrast --project is the project where the tests
  # spin up Kubeflow instances.
  parser.add_argument(
    "--testing_project", default="kubeflow-ci", type=str,
    help=("The cluster used for Argo workflows."))

  parser.add_argument(
    "--testing_cluster", default="kubeflow-testing", type=str,
    help=("The cluster used for Argo workflows."))

  parser.add_argument(
    "--testing_zone", default="us-east1-d", type=str,
    help=("The zone of the cluster used for Argo workflows."))

  parser.add_argument(
    "--max_age_hours", default=3, type=int, help=("The age of deployments to gc."))

  parser.add_argument(
    "--gc_backend_services", default=False, type=bool,
    help=("""Whether to GC backend services."""))

  parser.add_argument(
    "--max_wf_age_hours", default=7*24, type=int,
    help=("How long to wait before garbage collecting Argo workflows."))

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
  # Parser for health checks
  parser_health = subparsers.add_parser(
    "health_checks", help="Cleanup health checks")

  parser_health.set_defaults(func=cleanup_health_checks)

  ######################################################
  # Parser for service accounts
  parser_service_account = subparsers.add_parser(
    "service_accounts", help="Cleanup service accounts")

  parser_service_account.set_defaults(func=cleanup_service_accounts)

  ######################################################
  # Parser for service account bindings
  parser_service_account = subparsers.add_parser(
    "service_account_bindings", help="Cleanup service account bindings")

  parser_service_account.set_defaults(func=cleanup_service_account_bindings)

  ######################################################
  # Parser for certificates
  parser_certificates = subparsers.add_parser(
    "certificates", help="Cleanup certificates")

  parser_certificates.set_defaults(func=cleanup_certificates)

  ######################################################
  # Parser for auto deployments
  parser_auto_deployments = subparsers.add_parser(
    "auto_deployments", help="Cleanup auto deployments")

  add_deployments_args(parser_auto_deployments)
  parser_auto_deployments.set_defaults(func=cleanup_auto_deployments)

  ######################################################
  # Parser for deployments
  parser_deployments = subparsers.add_parser(
    "deployments", help="Cleanup deployments")

  add_deployments_args(parser_deployments)
  parser_deployments.set_defaults(func=cleanup_deployments)

  ######################################################
  # Parser for clusters
  parser_clusters = subparsers.add_parser(
    "clusters", help="Cleanup clusters")

  parser_clusters.add_argument(
    "--zones", default="us-east1-d,us-central1-a", type=str,
    help="Comma separated list of zones to check.")

  parser_clusters.set_defaults(func=cleanup_clusters)

  ######################################################
  # Parser for instance groups
  parser_ig = subparsers.add_parser(
      "instance_groups", help="Cleanup instance groups")
  add_deployments_args(parser_ig)
  parser_ig.set_defaults(func=cleanup_instance_groups)

  args = parser.parse_args()

  # Update max age
  MAX_LIFETIME[E2E_INFRA] = datetime.timedelta(hours=args.max_age_hours)

  logging.info("Max lifetime:\n%s", MAX_LIFETIME)

  util.maybe_activate_service_account()

  args.func(args)

if __name__ == "__main__":
  main()
