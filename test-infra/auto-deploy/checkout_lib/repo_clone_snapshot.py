"""Repositories checkout helper script.

Takes as input from latest blob in GCP storage bucket and checkout repositories
as requested.
"""

import argparse
import json
import logging
import os
import subprocess

import checkout_util

def main():
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)

  parser = argparse.ArgumentParser()

  parser.add_argument(
    "--src_dir", default="", type=str,
    help=("Directory to write repositories to."))

  parser.add_argument(
    "--project", default="kubeflow-ci", type=str, help=("The project."))

  parser.add_argument(
    "--zone", default="us-east1-d", type=str, help=("The zone to deploy in."))

  parser.add_argument(
    "--repo_owner", default="kubeflow", type=str, help=("Repository owner."))

  parser.add_argument(
    "--job_labels",
    default="/etc/pod-info/labels",
    type=str, help=("DownwardAPIVolumeFile for job labels."))

  parser.add_argument(
    "--nfs_path", default="", type=str, help=("GCP Filestore PVC mount path."))

  args = parser.parse_args()
  job_name = checkout_util.get_job_name(args.job_labels)
  snapshot_path = checkout_util.get_snapshot_path(args.nfs_path, job_name)

  logging.info("Job name: %s", job_name)
  logging.info("Reading: %s", snapshot_path)
  snapshot = json.load(open(os.path.join(snapshot_path, "snapshot.json"), "r"))
  logging.info("Snapshot: %s", str(snapshot))

  # gs_client = storage.Client(project=args.project)
  # bucket = gs_client.get_bucket(args.snapshot_bucket)

  # filenames = [b.name for b in bucket.list_blobs()]
  # if not filenames:
  #   msg = "Not able to find any snapshot files in " + args.snapshot_bucket
  #   logging.error(msg)
  #   raise RuntimeError(msg)

  # filenames.sort(reverse=True)
  # blob_name = filenames[0] # pylint: disable=unsubscriptable-object

  # snapshot = json.loads(bucket.get_blob(blob_name).download_as_string())

  # logging.info("Snapshot profile: %s", str(snapshot))
  # for repo in snapshot:
  #   logging.info("Checking out: %s at %s", repo, snapshot.get(repo, ""))
  #   subprocess.call(("/usr/local/bin/checkout-snapshot.sh"
  #                    " {src_dir} {repo_owner} {repo_name} {sha}").format(
  #                      src_dir=args.src_dir,
  #                      repo_owner=args.repo_owner,
  #                      repo_name=repo,
  #                      sha=snapshot.get(repo, ""),
  #                    ),
  #                   shell=True)

if __name__ == '__main__':
  main()
