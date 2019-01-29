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
    "--project", default="kubeflow-ci", type=str, help=("The project."))

  parser.add_argument(
    "--github_token_file",
    default="/secret/github-token/github_token",
    type=str, help=("The file containing Github API token."))


if __name__ == '__main__':
  main()
