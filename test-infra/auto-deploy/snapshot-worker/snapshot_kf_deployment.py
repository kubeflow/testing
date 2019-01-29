"""TODO(gabrielwen): DO NOT SUBMIT without one-line documentation for snapshot_kf_deployment.

TODO(gabrielwen): DO NOT SUBMIT without a detailed description of snapshot_kf_deployment.
"""

import argparse
import logging
import yaml

from github import Github

def main():
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)

  parser = argparse.ArgumentParser()

  parser.add_argument(
    "snapshot_repos", default="", type=str, nargs="*",
    help=("Repositories needed to take snapshot as list separated by comma."))

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


if __name__ == '__main__':
  main()
