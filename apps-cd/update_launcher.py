#!/usr/bin/python

"""A program to continuously launch Tekton pipelines.

This is a simple script to run update_kf_apps.py. The script does the following

1. Fetch the latest code from GitHub
2. Run update_kf_apps.py to submit Tekton PipelineRuns to update any apps
   that need it.
3. Sleep
4. Go back to step 1.


The reason for not calling update_kf_apps.py directly is that we want to
run a git sync to pick up the latest code.

The reason the code is not in py is because we don't want this script to
have any dependencies on the code in py since its just intended to be a
simple shell script
"""
import fire
import logging
import os
import subprocess
import time
from urllib import parse

DEFAULT_REPO = "https://github.com/kubeflow/testing.git"

class Launcher:
  @staticmethod
  def run(repo=DEFAULT_REPO, repo_dir= "/app/src/kubeflow/testing",
          sync_time_seconds=600, **update_args):
    """Run the program.

    Args:
    repo: Git URL to fetch the code. This should be a kubeflow/testing repo
      (or fork) and container the update_kf_apps.py code as well as the
      configs used with update_kf_appss.py. To specify a particular branch
      add a query arg "?ref=<branch_name>
    app_src_dir: Directory where repo should be checked out.
    sync_time_seconds: Time in seconds to wait between launches.
    update_args: Arguments for update_kf_apps
    """

    parent_dir = os.path.dirname(repo_dir)
    if not os.path.exists(parent_dir):
      os.makedirs(parent_dir)

    # Parse out the query args to look for a branch
    p = parse.urlparse(repo)
    query = p.query

    repo_url = p._replace(query="").geturl()

    ref = "master"
    if query:
      logging.info(f"URL has query string {query}")
      q = parse.parse_qs(p.query)
      logging.info(f"Parsed query {q}")
      if "ref" in q:
        ref = q["ref"][-1]

    logging.info(f"Using ref {ref}")
    while True:
      if not os.path.exists(repo_dir):
        logging.info(f"Cloning {repo}")
        subprocess.check_call(["git", "clone", repo_url, repo_dir])
      logging.info(f"Fetching latest code")
      subprocess.check_call(["git", "fetch", "origin"], cwd=repo_dir)

      logging.info(f"Checking out origin/{ref}")
      subprocess.check_call(["git", "checkout", f"origin/{ref}"], cwd=repo_dir)

      commit = subprocess.check_output(["git", "describe", "--tags",
                                        "--always", "--dirty"], cwd=repo_dir)

      logging.info(f"using update_kf_apps.py from {p.geturl()} "
                   f"at commit: {commit}")

      logging.info("Launching update_kf_apps")

      command = ["python", "-m", "kubeflow.testing.cd.update_kf_apps", "apply"]

      extra = [f"--{k}={v}" for k,v in update_args.items()]
      command.extend(extra)
      py_dir = os.path.join(repo_dir, "py")
      subprocess.check_call(command, cwd=py_dir)

      logging.info("Wait before rerunning")
      time.sleep(sync_time_seconds)

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(Launcher)
