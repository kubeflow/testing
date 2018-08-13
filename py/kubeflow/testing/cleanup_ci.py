"""Cleanup Kubeflow deployments in our ci system."""
import argparse
import datetime
import logging
import os
import re
import subprocess
import tempfile

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

# Regexes that select matching deployments
MATCHING = [re.compile("e2e-.*"), re.compile("kfctl.*")]

def is_match(name):
  for m in MATCHING:
    if m.match(name):
      return True

  return False

def main(): # pylint: disable=too-many-locals,too-many-statements
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--project", default="kubeflow-ci", type=str, help=("The project."))

  parser.add_argument(
    "--max_age_hours", default=3, type=int, help=("The age of deployments to gc."))

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

  args = parser.parse_args()

  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)

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
    # So we parse out the ours.
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

if __name__ == "__main__":
  main()
