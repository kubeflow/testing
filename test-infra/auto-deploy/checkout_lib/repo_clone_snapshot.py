"""Repositories checkout helper script.

Takes as input from latest blob in GCP storage bucket and checkout repositories
as requested.
"""

import argparse
import json
import logging
import os
import subprocess

def main():
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)

  parser = argparse.ArgumentParser()

  parser.add_argument(
    "--data_dir", default="", type=str, help=("Directory to store the data."))

  args = parser.parse_args()

  snapshot_path = os.path.join(args.data_dir, "snapshot.json")
  logging.info("Reading: %s", snapshot_path)
  snapshot = json.load(open(snapshot_path, "r"))
  logging.info("Snapshot: %s", str(snapshot))

  repos = snapshot.get("repos", [])

  for repo in repos:
    branch = repo.get("branch", "")
    sha = repo.get("sha", "")
    logging.info("Checking out: %s at branch %s with SHA %s", repo, branch, sha)

    target_dir = os.path.join(args.data_dir, repo["repo"])
    if os.path.exists(target_dir):
      logging.info("Directory %s already exists; not checking out repo",
                   repo["repo"])
      continue
    git_url = "https://github.com/{repo_owner}/{repo_name}.git".format(
        repo_owner=repo["owner"], repo_name=repo["repo"],)
    command = ["git", "clone", "--single-branch", "--branch", branch,
               git_url, repo["repo"]]
    logging.info("Executing: %s", command)
    subprocess.check_call(command, cwd=args.data_dir)

    logging.info("Taking snapshot at %s", sha)
    command = ["git", "reset", "--hard", sha]
    logging.info("Executing: %s", command)
    subprocess.check_call(command, cwd=os.path.join(args.data_dir,
                                                    repo["repo"]))

if __name__ == '__main__':
  main()
