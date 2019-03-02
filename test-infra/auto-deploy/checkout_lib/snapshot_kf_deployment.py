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

import checkout_util

import googleapiclient
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

def get_deployment_name(project, base_name, max_num):
  """Retrieve deployment metadata from GCP and choose the oldest cluster.

  Args:
    project: Name of GCP project.
    base_name: Base name of clusters.
    max_num: Maximum number of deployments

  Returns:
    Name to use for the deployment
  """
  credentials = GoogleCredentials.get_application_default()

  dm = discovery.build("deploymentmanager", "v2", credentials=credentials)
  manifests_client = dm.manifests()
  dm_client = dm.deployments()

  matching = {}

  next_page_token = None

  m = re.compile(base_name + "-n\d\d$")
  while True:
    deployments = dm_client.list(project=project,
                                 pageToken=next_page_token).execute()

    for d in deployments["deployments"]:
      if m.match(d["name"]):
        matching[d["name"]] = d

    if "nextPageToken" not in deployments:
      break
    next_page_token = deployments["nextPageToken"]

  # Check if there any any unused deployments.

  allowed = set()
  for num in range(max_num):
    allowed.add("{0}-n{1:02d}".format(base_name, num))

  remaining = sorted(allowed - set(matching.keys()))

  if remaining:
    return remaining[0]

  # Sort matching items by create time
  results = matching.values()
  results.sort(key=lambda x: x.get("insertTime", ""))
  return results[0]["name"]

def repo_snapshot_hash(github_token, repo_owner, repo, branch, snapshot_time):
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
  params = {"until": snapshot_time, "sha": branch}

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

def lock_and_write(target, payload):
  dirname = os.path.dirname(target)
  if not os.path.exists(dirname):
    os.makedirs(dirname)
  file_lock = filelock.FileLock(os.path.join(dirname, "file.lock"))
  with file_lock:
    if os.path.exists(target):
      return
    logging.info("Writing to file: %s", target)
    with open(target, "w") as f:
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
    "--snapshot_repos", type=str,
    help=("A semi-colon separated list of repositories to check out."
          "{ORG}/{REPO}@{BRANCH};{ORG2}/{REPO2}@{BRANCH}"
          "If branch is none master is used."))

  parser.add_argument(
    "--base_name", default="kf-v0-4", type=str,
    help=("The base name for the deployment typically kf-vX-Y or kf-vmaster."))

  parser.add_argument(
    "--max_cluster_num", default=1, type=int,
    help=("Max number for testing cluster(s)."))

  parser.add_argument(
    "--project", default="kubeflow-ci", type=str, help=("The GCP project."))

  parser.add_argument(
    "--github_token_file",
    default="",
    type=str, help=("The file containing Github API token."))

  parser.add_argument(
    "--job_labels",
    default="",
    type=str, help=("DownwardAPIVolumeFile for job labels."))

  parser.add_argument(
    "--data_dir",
    default="", type=str, help=("Directory where data shoud be written."))

  args = parser.parse_args()
  github_token = None
  if args.github_token_file:
    logging.info("Reading GITHUB_TOKEN from file: %s", args.github_token_file)
    token_file = open(args.github_token_file, "r")
    github_token = token_file.readline()
    token_file.close()
  else:
    logging.info("Looking for GITHUB token in environment variable "
                 "GITHUB_TOKEN")
    github_token = os.getenv("GITHUB_TOKEN", "")

  if not github_token:
    raise ValueError("No GITHUB token set")

  name = get_deployment_name(args.project, args.base_name, args.max_cluster_num)

  logging.info("Using deployment name %s", name)

  job_name = ""
  if args.job_labels:
    logging.info("Reading labels form file %s", args.job_labels)
    job_name = checkout_util.get_job_name(args.job_labels)

  logging.info("Job name: %s", job_name)
  logging.info("Repos: %s", str(args.snapshot_repos))
  logging.info("Project: %s", args.project)

  snapshot_time = datetime.datetime.utcnow().isoformat()
  logging.info("Snapshotting at %s", snapshot_time)

  repo_snapshot = {
    "timestamp": snapshot_time,
    "name": name,
    "repos": [],
  }
  for repo_path in args.snapshot_repos.split(";"):
    if "@" in repo_path:
      repo, branch = repo_path.split("@")
    else:
      repo = repo_path
      branch = "master"

    repo_org, repo_name = repo.split("/")
    sha = repo_snapshot_hash(github_token, repo_org, repo_name, branch,
                             snapshot_time)
    logging.info("Snapshot repo %s at %s, branch is %s", repo, sha, branch)
    repo_snapshot["repos"].append({
      "owner": repo_org,
      "repo": repo_name,
      "sha": sha,
      "branch": branch
    })

  logging.info("Snapshot = %s", str(repo_snapshot))
  snapshot_path = os.path.join(args.data_dir, "snapshot.json")
  lock_and_write(snapshot_path, json.dumps(repo_snapshot))


if __name__ == '__main__':
  main()
