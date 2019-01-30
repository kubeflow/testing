"""To snapshot Github repositories and put commit SHA into files.

Output file will have file name with the timestamp snapshot is taken.
Content of file will be key value pairs in the format of JSON, where key
is the name of repository and value is the SHA snapshot is taken.
"""

import argparse
import datetime
import json
import logging
import requests
import subprocess

from google.cloud import storage

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
  params = { "until": snapshot_time }

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

  if len(sha_time) == 0:
    msg = ("Not able to find valid commit SHA for repo {0}/{1}"
           "with given time {2}").format(repo_owner, repo, snapshot_time)
    logging.error(msg)
    raise RuntimeError(msg)

  def sort_by_time(record):
    return record.get("commit_date", "")
  sha_time.sort(key=sort_by_time, reverse=True)

  return sha_time[0].get("sha", "")

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
    "--output_bucket",
    default="kubeflow-ci_deployment-snapshot",
    type=str, help=("GCP bucket output is writing to."))

  args = parser.parse_args()
  token_file = open(args.github_token_file, "r")
  github_token = token_file.readline()
  token_file.close()

  subprocess.call(("gcloud auth activate-service-account"
                   " --key-file=$GOOGLE_APPLICATION_CREDENTIALS"),
                  shell=True)
  subprocess.call("gcloud config list", shell=True)

  logging.info("Repos: %s", str(args.snapshot_repos))
  logging.info("Project: %s", args.project)
  logging.info("Repo owner: %s", args.repo_owner)

  snapshot_time = datetime.datetime.utcnow().isoformat()
  logging.info("Snapshotting at %s", snapshot_time)

  repo_snapshot = {}
  for repo in args.snapshot_repos:
    sha = repo_snapshot_hash(github_token, args.repo_owner, repo, snapshot_time)
    logging.info("Snapshot repo %s at %s", repo, sha)
    repo_snapshot[repo] = sha

  gs_client = storage.Client(project=args.project)
  bucket = gs_client.get_bucket(args.output_bucket)
  blob = bucket.blob(snapshot_time + ".json")
  blob.upload_from_string(json.dumps(repo_snapshot))


if __name__ == '__main__':
  main()
