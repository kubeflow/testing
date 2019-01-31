"""Repositories checkout helper script.

Takes as input from latest blob in GCP storage bucket and checkout repositories
as requested.
"""

import argparse
import json
import logging
import os
import subprocess

from google.cloud import storage

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
    "--snapshot_bucket",
    default="kubeflow-ci_deployment-snapshot",
    type=str, help=("GCP bucket snapshot files written to."))

  args = parser.parse_args()
  gs_client = storage.Client(project=args.project)
  bucket = gs_client.get_bucket(args.snapshot_bucket)

  filenames = [b.name for b in bucket.list_blobs()]
  if not filenames:
    msg = "Not able to find any snapshot files in " + args.snapshot_bucket
    logging.error(msg)
    raise RuntimeError(msg)

  filenames.sort(reverse=True)
  blob_name = filenames[0] # pylint: disable=unsubscriptable-object

  snapshot = json.loads(bucket.get_blob(blob_name).download_as_string())

  # TODO(gabrielwen): Read deployment_num from blob after it's written.
  metadata = {
    "labels": {
      "snapshot_data": blob_name,
    },
    "deployment_num": 0
  }

  if not os.path.exists(args.src_dir):
    os.makedirs(args.src_dir)
  with open(os.path.join(args.src_dir, "deployment_metadata.json"), "w") as f:
    f.write(json.dumps(metadata))

  logging.info("Snapshot profile: %s", str(snapshot))
  for repo in snapshot:
    logging.info("Checking out: %s at %s", repo, snapshot.get(repo, ""))
    subprocess.call(("/usr/local/bin/checkout-snapshot.sh"
                     " {src_dir} {repo_owner} {repo_name} {sha}").format(
                       src_dir=args.src_dir,
                       repo_owner=args.repo_owner,
                       repo_name=repo,
                       sha=snapshot.get(repo, ""),
                     ),
                    shell=True)

if __name__ == '__main__':
  main()
