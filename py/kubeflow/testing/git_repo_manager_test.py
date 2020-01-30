import collections
import difflib
import logging
import os
import pprint
import yaml

from kubeflow.testing import github_repo_manager # pylint: disable=no-name-in-module

import pytest


def test_parse_git_url():
  result = github_repo_manager._parse_git_url("git@github.com:kubeflow/manifests.git") # pylint: disable=protected-access

  assert result == update_kf_apps.GIT_TUPLE("git@github.com", "kubeflow",
                                            "manifests")
if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  pytest.main()

