"""A python script to run Tekton pipelines to update Kubeflow manifests."""

import fire
import collections
import logging
import os
import re
import yaml

from kubeflow.testing import util

GIT_URL_RE = re.compile(r"([^:]*):([^/]*)/([^\.]*)\.git")

GIT_TUPLE = collections.namedtuple("git_tuple", ("host", "owner", "repo"))

APP_VERSION_TUPLE = collections.namedtuple("app_version", ("app", "version"))

def _combine_params(left, right):
  """Combine to lists of name,value pairs."""

  d = {}
  for p in left:
    d[p["name"]] = p

  for p in right:
    d[p["name"]] = p

  result = []

  for _, v in d.items():
    result.append(v)

  return result

def _sync_repos(repos, src_dir):
  """Make sure all the repositories are checked out to src dir and up to date."""

  if not os.path.exists(src_dir):
    os.makedirs(src_dir)

  for r in repos:
    url = _get_param(r["resourceSpec"]["params"], "url")

    if not url:
      raise ValueError(f"Repository {r['name']} is missing param url")

    url = url["value"]
    repo = _parse_git_url(url)

    repo_dir = os.path.join(src_dir, repo.owner, repo.repo)
    if not os.path.exists(repo_dir):
      if not os.path.exists(os.path.join(src_dir, repo.owner)):
        os.makedirs(os.path.join(src_dir, repo.owner))
      logging.info(f"Clone {url}")
      util.run(["git", "clone", url, repo.repo],
               cwd=os.path.join(src_dir, repo.owner))

    logging.info("Sync repo {url}")

    util.run(["git", "fetch", "origin"],
             cwd=os.path.join(src_dir, repo.owner, repo.repo))

def _parse_git_url(url):
  m = GIT_URL_RE.match(url)

  if not m:
    return GIT_TUPLE("", "", "")

  return GIT_TUPLE(m.group(1), m.group(2), m.group(3))

def _last_commit(branch, repo_root, path):
  """Get the last commit of a change to the source.

  Args:
    branch: The branch e.g. origin/master
    path: The relative path
  """
  util.run(["git", "checkout", branch], cwd=repo_root)
  output = util.run(["git", "log", "-n", "1", "--pretty=format:\"%h\"", path],
                    cwd=repo_root)

  return output.strip('"')

def _get_param(params, name):
  for p in params:
    if p["name"] == name:
      return p
  return None

def _param_index(params, name):
  """Return the index of the specified item"""
  for i, p in enumerate(params):
    if p["name"] == name:
      return i
  raise LookupError(f"Missing item with name={name}")

def _build_run(app_run, app, version, commit):
  """Create a PipelineRun spec.

  Args:
    app_run: A pipelinerun to use as the template
    app: The application configuration
    version: The version specification
    commit: The specific commit at which to build the source image.
    tag: The tag for the image
  """
  app_run["metadata"]["generateName"] = f"cd-{app['name']}-{commit}"

  # Override the params
  app_run["spec"]["params"] = _combine_params(app_run["spec"]["params"],
                                              app["params"])

  # Override the repositories
  app_run["spec"]["resources"] = _combine_params(app_run["spec"]["resources"],
                                                 version["repos"])

  # Override the commit for the src repo to pin to a specific commit
  source_index = _param_index(app_run["spec"]["resources"], app["sourceRepo"])
  source_params = app_run["spec"]["resources"][source_index]["resourceSpec"]["params"]

  updated_params = _combine_params(source_params, [{
                                                   "name": "revision",
                                                   "value": commit,}])

  app_run["spec"]["resources"][source_index]["resourceSpec"]["params"] = updated_params

  # Override the image resource
  tag = f"{version['tag']}-g{commit}"

  image_resource = _get_param(app_run["spec"]["resources"], "image")

  src_image_url = _get_param(app["params"], "src_image_url")["value"]

  if not src_image_url:
    raise ValueError(f"App {app['name']} is missing parameter "
                     f"src_image_url")

  image_resource["resourceSpec"]["params"] = _combine_params(
    image_resource["resourceSpec"]["params"],
    [{
      "name": "url",
      "value": f"{src_image_url}:{tag}",
    }]
  )

  app_run["spec"]["resources"] = _combine_params(app_run["spec"]["resources"],
                                                 [image_resource])

  return app_run


def _deep_copy(data):
  value = yaml.dump(data)
  return yaml.load(value)

def _handle_app(run, app, version, src_dir, output_dir):
  app_version = AppVersion(app, version)

  # Get the last change to the source
  src_path = _get_param(app["params"], "path_to_context")["value"]

  if not src_path:
    raise ValueError(f"App {app['name']} is missing parameter "
                     f"path_to_context")


  repo_root = os.path.join(src_dir, app_version.repo.owner,
                           app_version.repo.repo)

  src_branch = _get_param(app_version.source_repo["resourceSpec"]["params"],
                                "revision")["value"]
  branch_spec = f"origin/{src_branch}"
  commit = _last_commit(branch_spec, repo_root, src_path)

  run = _build_run(run, app, _deep_copy(version), commit)

  if not os.path.exists(output_dir):
    os.makedirs(output_dir)
  output_file = os.path.join(output_dir,
                                   f"{app['name']}-run-{src_branch}-"
                                   f"{commit}.yaml")
  logging.info(f"Writing run for App: {app['name']} Version: "
                     f"{version['name']} to file {output_file}")
  with open(output_file, "w") as hf:
    yaml.dump(run, hf)

class UpdateKfApps:

  @staticmethod
  def create_runs(config, output_dir, template, src_dir):
    """Create the pipeline runs.

    Args:
      config: The path to the configuration
      output_dir: Directory where pipeline runs should be written
      template: The path to the YAML file to act as a template
      src_dir: Directory where source should be checked out
    """

    with open(config) as hf:
      run_config = yaml.load(hf)

    failures = []
    # Loop over the cross product of versions and applications and generate
    # a run for each one.
    for version in run_config["versions"]:
      _sync_repos(version["repos"], src_dir)

      for app in run_config["applications"]:
        # Load a fresh copy of the template
        with open(template) as hf:
          run = yaml.load(hf)

        # Make copies of app and version so that we don't end up modifying them
        try:
          _handle_app(run, _deep_copy(app), _deep_copy(version), src_dir,
                      output_dir)
        except (ValueError, LookupError) as e:
          failures.append(APP_VERSION_TUPLE(app["name"], version["name"]))
          logging.error(f"Exception occured creating run for "
                        f"App: {app['name']} Version: {version['name']} "
                        f"Exception: {e}")

    if failures:
      failed = [f"(App:{i.app}, Version:{i.version})" for i in failures]
      failed = ", ".join(failed)
      logging.error(f"Failed to generate pipeline runs for: {failed}")
    else:
      logging.info("Succcessfully created pipeline runs for all apps and "
                   "versions")

class AppVersion:
  """App version is a wrapper around a combination of application and version.
  """

  def __init__(self, app, version):
    """Construct the AppVersion instance.

    Args:
      app: A dictionary representing the app
      version: dictionary representing the version
    """

    self.source_repo = None
    for r in version["repos"]:
      if r["name"] == app["sourceRepo"]:
        self.source_repo = r

    if not self.source_repo:
      raise ValueError(f"App {app['name']} uses repo {app['sourceRepo']} "
                       f"but this repo was not defined in version "
                       f"{version['name']}")

    self.branch = _get_param(self.source_repo["resourceSpec"]["params"], "revision")

    url = _get_param(self.source_repo["resourceSpec"]["params"], "url")

    if not url:
      raise ValueError(f"Repository {self.source_repo['name']} is missing "
                       f"param url")

    self.url = url["value"]
    self.repo = _parse_git_url(self.url)

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(UpdateKfApps)
