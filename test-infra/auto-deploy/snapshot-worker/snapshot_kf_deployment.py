"""TODO(gabrielwen): DO NOT SUBMIT without one-line documentation for snapshot_kf_deployment.

TODO(gabrielwen): DO NOT SUBMIT without a detailed description of snapshot_kf_deployment.
"""

import argparse
import datetime
import json
import logging
import requests
import yaml

def repo_snapshot_hash(github_token, repo_owner, repo, snapshot_time):
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

  args = parser.parse_args()
  token_file = open(args.github_token_file, "r")
  github_token = token_file.readline()
  token_file.close()

  logging.info("Repos: %s", str(args.snapshot_repos))
  logging.info("Project: %s", args.project)
  logging.info("Repo owner: %s", args.repo_owner)

  snapshot_time = datetime.datetime.utcnow().isoformat()
  logging.info("Snapshotting at %s", snapshot_time)

  for repo in args.snapshot_repos:
    sha = repo_snapshot_hash(github_token, args.repo_owner, repo, snapshot_time)
    logging.info("Snapshot repo %s at %s", repo, sha)

if __name__ == '__main__':
  main()
