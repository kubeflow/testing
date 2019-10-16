"""Cleanup Kubeflow deployments in our ci system."""
# pylint: disable=too-many-lines
import argparse
import datetime
from dateutil import parser as date_parser
import logging
import os
import re
import retrying
import socket
import subprocess
import sys
import traceback
import tempfile
import time
import yaml

from cryptography import x509
from cryptography.hazmat.backends import default_backend

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
MATCHING_DISK = [re.compile(".*jlewi.*"), re.compile(".*kfctl.*"),
                 re.compile(".*postsubmit.*"), re.compile(".*presubmit.*"),
                 ]

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
        if not is_match_disk(name):
          unmatched.append(name)
          continue

        age = getAge(d["creationTimestamp"])
        if age > datetime.timedelta(hours=args.max_age_hours):
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

def cleanup_instance_groups(args):
  if not args.gc_backend_services:
    return

  credentials = GoogleCredentials.get_application_default()
  compute = discovery.build('compute', 'v1', credentials=credentials)
  instanceGroups = compute.instanceGroups()
  next_page_token = None
  expired = []
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
        if age > datetime.timedelta(
          hours=args.max_ci_deployment_resource_age_hours):
          logging.info("Deleting instanceGroups: %s, age = %r", name, age)
          if not args.dryrun:
            try:
              response = instanceGroups.delete(project=args.project,
                                              zone=zone,
                                              instanceGroup=name).execute()
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

  logging.info("Unexpired instance groups:\n%s", "\n".join(unexpired))
  logging.info("Deleted expired instance groups:\n%s", "\n".join(expired))
  logging.info("Expired but in-use instance groups:\n%s", "\n".join(in_use))

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
      if age > datetime.timedelta(
        hours=args.max_ci_deployment_resource_age_hours):
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

  while True:
    results = targetHttpsProxies.list(project=args.project,
                                      pageToken=next_page_token).execute()
    if not "items" in results:
      break
    for s in results["items"]:
      name = s["name"]
      age = getAge(s["creationTimestamp"])
      if age > datetime.timedelta(
        hours=args.max_ci_deployment_resource_age_hours):
        logging.info("Deleting urlMaps: %s, age = %r", name, age)
        if not args.dryrun:
          try:
            response = targetHttpsProxies.delete(
              project=args.project, targetHttpsProxy=name).execute()
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
      if age > datetime.timedelta(
        hours=args.max_ci_deployment_resource_age_hours):
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
      if age > datetime.timedelta(hours=args.max_forwarding_rules_age_hours):
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

  unfinished_ops = wait_ops_max_mins(compute.globalOperations(), args, delete_ops, 20)
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
      if age > datetime.timedelta(
        hours=args.max_ci_deployment_resource_age_hours):
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

def cleanup_certificates(args):
  credentials = GoogleCredentials.get_application_default()

  compute = discovery.build('compute', 'v1', credentials=credentials)
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
      # TODO(jlewi): Using a max duration of 7 days is a bit of a hack.
      # Certificates created for pre/postsubmits should be expired after
      # a couple hours. But the auto-deployments e.g. kf-vmaster... should
      # last for a couple of days. So we should really be looking at the
      # host and adjusting the timeout. But the results in the certificates
      # don't tell us what the hostname is. gcloud returns the host though
      # so the information should be somewhere. Maybe we just need a newer
      # version of the API?
      #
      # If we decode the pem it should be inter
      name = d["name"]

      if not "certificate" in d:
        logging.warning("Certificate %s is missing certificate", name)
        continue

      raw_certificate = d["certificate"]

      cert = x509.load_pem_x509_certificate(raw_certificate.encode('utf-8'), default_backend())

      # TODO(jlewi): Is there a way to do this without accessing protected attributes
      domain = cert.subject._attributes[0]._attributes[0].value # pylint: disable=protected-access

      # Expire e2e certs after 4 hours
      if domain.startswith("kfct"):
        max_age = datetime.timedelta(hours=4)
      else:
        # For autodeployments delete after seven days
        max_age = datetime.timedelta(days=7)

      if age > max_age:
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
  logging.info("Finished cleanup service accounts")

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
      logging.info("Delete binding for members:\n%s", "\n".join(
        members_to_delete))
  iamPolicy['bindings'] = keepBindings

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
  trim_unused_bindings(iamPolicy, accounts)

  setBody = {'policy': iamPolicy}
  if not args.dryrun:
    resourcemanager.projects().setIamPolicy(resource=args.project, body=setBody).execute()

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
def wait_ops_max_mins(operation_resource, args, ops, max_wait_mins=15):
  end_time = datetime.datetime.now() + datetime.timedelta(minutes=max_wait_mins)

  while datetime.datetime.now() < end_time and ops:
    not_done = []
    for op in ops:
      op = operation_resource().get(project=args.project, operation=op["name"]).execute()
      status = op.get("status", "")
      if status != "DONE":
        not_done.append(op)
    ops = not_done
    if not ops:
      time.sleep(30)
  return ops

def cleanup_deployments(args): # pylint: disable=too-many-statements,too-many-branches
  logging.info("Cleanup deployments")

  credentials = GoogleCredentials.get_application_default()
  dm = discovery.build("deploymentmanager", "v2", credentials=credentials)

  deployments_client = dm.deployments()
  deployments = deployments_client.list(project=args.project).execute()

  unexpired = []
  expired = []

  delete_ops = []
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

    if "error" in d.get("operation", {}):
      # Prune failed deployments more aggressively
      logging.info("Deployment %s is in error state %s",
                   d.get("name"), d.get("operation").get("error"))
      max_age = datetime.timedelta(minutes=10)
    else:
      max_age = datetime.timedelta(hours=args.max_age_hours)

    if age < max_age:
      unexpired.append(name)
      logging.info("Deployment %s has not expired", name)
      continue

    logging.info("Deployment %s has expired", name)
    expired.append(name)
    logging.info("Deleting deployment %s", name)

    if not args.dryrun:
      try:
        op = deployments_client.delete(project=args.project, deployment=name).execute()
        delete_ops.append(op)
      except Exception as e:
        # Keep going on error because we want to delete the other deployments.
        # TODO(jlewi): Do we need to handle cases by issuing delete with abandon?
        logging.error("There was a problem deleting deployment %s; error %s", name, e)
  delete_ops = wait_ops_max_mins(dm.operations(), args, delete_ops, max_wait_mins=15)
  not_done_names = [op["name"] for op in delete_ops]

  logging.info("Delete ops that didn't finish:\n%s", "\n".join(not_done_names))
  logging.info("Unexpired deployments:\n%s", "\n".join(unexpired))
  logging.info("expired deployments:\n%s", "\n".join(expired))
  logging.info("Finished cleanup deployments")

def cleanup_clusters(args):
  logging.info("Cleanup deployments")
  credentials = GoogleCredentials.get_application_default()
  gke = discovery.build("container", "v1", credentials=credentials)

  # Collect clusters for which deployment might no longer exist.
  clusters_client = gke.projects().zones().clusters()

  expired = []
  unexpired = []
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
        expired.append(name)
        logging.info("Deleting cluster %s in zone %s", name, zone)

        if not args.dryrun:
          clusters_client.delete(projectId=args.project, zone=zone,
                                 clusterId=name).execute()

      else:
        unexpired.append(name)
  logging.info("Unexpired clusters:\n%s", "\n".join(unexpired))
  logging.info("expired clusters:\n%s", "\n".join(expired))
  logging.info("Finished cleanup clusters")

# The order of cleanup_forwarding_rules, cleanup_target_http_proxies,
# cleanup_url_maps, cleanup_backend_services, cleanup_instance_groups makes
# sure ingress resources are GCed in one run of this script. See
# https://github.com/kubernetes/ingress-gce/issues/136#issuecomment-371254595

def cleanup_all(args):
  ops = [# Deleting deploymens should be called first because hopefully that will
         # cleanup all the resources associated with the deployment
         cleanup_deployments,
         cleanup_clusters,
         cleanup_endpoints,
         cleanup_certificates,
         cleanup_service_accounts,
         cleanup_service_account_bindings,
         cleanup_workflows,
         cleanup_disks,
         cleanup_forwarding_rules,
         cleanup_target_https_proxies,
         cleanup_target_http_proxies,
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
    help=("""Whether to GC backend services that are older
          than --max_ci_deployment_resource_age_hours."""))

  parser.add_argument(
    "--max_ci_deployment_resource_age_hours",
    default=24, type=int,
    help=("The age of resources in kubeflow-ci-deployment to gc."))

  parser.add_argument(
    "--max_forwarding_rules_age_hours",
    default=12, type=int,
    help=("The age of forwarding rules in kubeflow-ci-deployment to gc."))

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
