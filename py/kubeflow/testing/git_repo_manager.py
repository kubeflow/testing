"""Utilities for managing and working with Git repositories."""

import collections
import logging
import os
import re
import tempfile

from kubeflow.testing import util

GIT_URL_RE = re.compile(r"([^:]*):([^/]*)/([^\.]*)\.git")
GIT_TUPLE = collections.namedtuple("git_tuple", ("host", "owner", "repo"))

def parse_git_url(url):
  """Parse a github url."""
  m = GIT_URL_RE.match(url)

  if not m:
    return GIT_TUPLE("", "", "")

  return GIT_TUPLE(m.group(1), m.group(2), m.group(3))

class GitRepoManager:
  """Manage a clone of a repository."""

  def __init__(self, url=None, local_dir=None, remote_name="origin"):
    """Initialize the GitRepoManager.

    Args:
      url: The URL to clone
      local_dir: (Optional) Local directory to check it out to. If not
        specified a temporay directory is used. If the directory
        exists it should already be a clone of the repo (we currently don't
        check)
    """

    self.url = url
    self.local_dir = local_dir
    if not local_dir:
      self.local_dir = tempfile.mkdtemp(prefix="GitRepoManager_")

      # This is a bit of a hack. Should do something more elegant in terms
      # of the name where it will be cloned.
      name = parse_git_url(url)
      self.local_dir = os.path.join(self.local_dir, name.owner, name.repo)

    self.remote_name = remote_name

  def _run_git(self, *args):
    """Run a subprocess command inside the repo directory."""
    return util.run(*args, cwd=self.local_dir)

  def fetch(self):
    """Fetch latest changes."""
    # TODO(jlewi): We should really check if there is a remote pointing
    # at the URL and if not add one

    parent_dir = os.path.dirname(self.local_dir)
    if not os.path.exists(parent_dir):
      logging.info(f"Creating directory {parent_dir}")
      os.makedirs(parent_dir)

    if not os.path.exists(self.local_dir):
      logging.info(f"Clone {self.url}")
      util.run(["git", "clone", self.url, self.local_dir])

    self._run_git(["git", "fetch", self.remote_name])

  def last_commit(self, branch, path):
    """Get the last commit of a change to the source.

    Args:
      branch: The branch in the form {remote_name}/{branch}

      path: The relative path
    """

    self._run_git(["git", "checkout", branch])

    command = ["git", "log", "-n", "1", "--pretty=format:\"%h\""]

    if path:
      command.append(path)

    output = self._run_git(command)

    return output.strip('"')
