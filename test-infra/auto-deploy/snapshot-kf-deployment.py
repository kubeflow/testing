"""To snapshot Github repositories and put commit SHA into files.

Output file will have file name with the timestamp snapshot is taken.
Content of file will be key value pairs in the format of JSON, where key
is the name of repository and value is the SHA snapshot is taken.
"""

import argparse
import datetime
import filelock
import json
import logging
import os
import re
import requests
import subprocess

from google.cloud import storage

JOB_NAME_REGEX = re.compile("job-name=\"([a-z0-9-]+)\"")

def find_job_name(line):
  job_name = JOB_NAME_REGEX.match(line)
  return job_name.group(1) if job_name and job_name.group(1) else ""

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

  labels = open(args.job_labels, "r")
  job_name = ""
  for line in labels.readlines():
    logging.info("Line = %s", line)
    job_name = find_job_name(line)
    logging.info("job_name = %s", job_name)
    if job_name:
      logging.info("break")
      break

  if not job_name:
    msg = "Not able to find job_name from labels."
    logging.error(msg)
    raise RuntimeError(msg)

  logging.info("Repos: %s", str(args.snapshot_repos))
  logging.info("Project: %s", args.project)
  logging.info("Repo owner: %s", args.repo_owner)

  snapshot_time = datetime.datetime.utcnow().isoformat()
  logging.info("Snapshotting at %s", snapshot_time)

  # TODO(gabrielwen): Add deploying cluster num.
  repo_snapshot = {
    "timestamp": snapshot_time,
    "repos": {},
  }
  for repo in args.snapshot_repos:
    sha = repo_snapshot_hash(github_token, args.repo_owner, repo, snapshot_time)
    logging.info("Snapshot repo %s at %s", repo, sha)
    repo_snapshot["repos"][repo] = sha

  folder = os.path.join(args.nfs_path, "deployment-snapshot/runs", job_name)
  lock_and_write(folder, json.dumps(repo_snapshot))


if __name__ == '__main__':
  main()
