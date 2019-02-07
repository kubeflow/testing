"""To snapshot Github repositories and put commit SHA into files.

Output file will have file name with the timestamp snapshot is taken.
Content of file will be key value pairs in the format of JSON, where key
is the name of repository and value is the SHA snapshot is taken.
"""

import argparse
import datetime
import filelock
import inspect
import json
import logging
import os
import requests

import checkout_util

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

def get_cluster_labels(project, cluster_names):
  logging.info("%s get_cluster_labels %s", project, str(cluster_names))
  credentials = GoogleCredentials.get_application_default()
  dm = discovery.build("deploymentmanager", "v2", credentials=credentials)
  logging.info(dm.deployments())
  deployments_client = dm.deployments()
  logging.info(inspect.getsource(deployments_client.get))
  for name in cluster_names:
    logging.info("%s: get %s", project, name)
    info = deployments_client.get(project, name)
    logging.info("Info returned: %s", str(info))

def repo_snapshot_hash(github_token, repo_owner, repo, snapshot_time):
  """Look into commit history and pick the latest commit SHA.

  Args:
    github_token: Github API token as string.
    repo_owner: Owner of repository.
    repo: Name of repository to take snapshot.
    snapshot_time: Time to cut snapshot in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ).

  Returns:
    sha: Commit hash.
  """
  headers = {
    "Authorization": "token " + github_token
  }
  url = ("https://api.github.com/repos/{owner}/{repo}/commits").format(
          owner=repo_owner, repo=repo)
  params = {"until": snapshot_time}

  r = requests.get(url, headers=headers, params=params, verify=False)
  if r.status_code != requests.codes.OK:
    msg = "Request to {0} returns: {1}".format(url, r.status_code)
    logging.error(msg)
    raise RuntimeError(msg)

  commits = json.loads(r.content)
  sha_time = []
  for commit in commits:
    sha_time.append({
      "sha": commit.get("sha", ""),
      "commit_date": commit.get("commit", {}).get("author", {}).get("date", ""),
    })
  sha_time = filter(lambda record: record.get("sha", "") and
                                   record.get("commit_date", ""),
                    sha_time)

  if not sha_time:
    msg = ("Not able to find valid commit SHA for repo {0}/{1}"
           "with given time {2}").format(repo_owner, repo, snapshot_time)
    logging.error(msg)
    raise RuntimeError(msg)

  def sort_by_time(record):
    return record.get("commit_date", "")
  sha_time.sort(key=sort_by_time, reverse=True)

  return sha_time[0].get("sha", "") # pylint: disable=unsubscriptable-object

def lock_and_write(folder, payload):
  dirname = os.path.dirname(folder)
  dir_lock = filelock.FileLock(os.path.join(dirname, "dir.lock"))
  with dir_lock:
    if not os.path.exists(folder):
      os.makedirs(folder)
  file_lock = filelock.FileLock(os.path.join(folder, "file.lock"))
  with file_lock:
    path = os.path.join(folder, "snapshot.json")
    if os.path.exists(path):
      return
    logging.info("Writing to file: %s", path)
    with open(path, "w") as f:
      f.write(payload)


def main():
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)

  parser = argparse.ArgumentParser()

  parser.add_argument(
    "snapshot_repos", nargs="+", help=("Repositories needed to take snapshot."))

  parser.add_argument(
    "--project", default="kubeflow-ci", type=str, help=("The GCP project."))

  parser.add_argument(
    "--repo_owner", default="kubeflow", type=str, help=("Github repo owner."))

  parser.add_argument(
    "--github_token_file",
    default="/secret/github-token/github_token",
    type=str, help=("The file containing Github API token."))

  parser.add_argument(
    "--job_labels",
    default="/etc/pod-info/labels",
    type=str, help=("DownwardAPIVolumeFile for job labels."))

  parser.add_argument(
    "--nfs_path",
    default="", type=str, help=("GCP Filestore PVC mount path."))

  args = parser.parse_args()
  token_file = open(args.github_token_file, "r")
  github_token = token_file.readline()
  token_file.close()

  get_cluster_labels(args.project, [
    "kf-v0-4-n00", "kf-v0-4-n01", "kf-v0-4-n02",
  ])

  job_name = checkout_util.get_job_name(args.job_labels)

  logging.info("Job name: %s", job_name)
  logging.info("Repos: %s", str(args.snapshot_repos))
  logging.info("Project: %s", args.project)
  logging.info("Repo owner: %s", args.repo_owner)

  snapshot_time = datetime.datetime.utcnow().isoformat()
  logging.info("Snapshotting at %s", snapshot_time)

  # TODO(gabrielwen): Add logic to choose deploying cluster_num.
  repo_snapshot = {
    "timestamp": snapshot_time,
    "cluster_num": 1,
    "repos": {},
  }
  for repo in args.snapshot_repos:
    sha = repo_snapshot_hash(github_token, args.repo_owner, repo, snapshot_time)
    logging.info("Snapshot repo %s at %s", repo, sha)
    repo_snapshot["repos"][repo] = sha

  folder = checkout_util.get_snapshot_path(args.nfs_path, job_name)
  lock_and_write(folder, json.dumps(repo_snapshot))


if __name__ == '__main__':
  main()
