"""A python script to run Tekton pipelines to update Kubeflow manifests."""

import fire
import collections
import logging
import os
import re
import yaml

from kubeflow.testing import util
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client import rest

GIT_URL_RE = re.compile(r"([^:]*):([^/]*)/([^\.]*)\.git")

GIT_TUPLE = collections.namedtuple("git_tuple", ("host", "owner", "repo"))

APP_VERSION_TUPLE = collections.namedtuple("app_version", ("app", "version"))

IMAGE_TUPLE = collections.namedtuple("image", ("name", "tag", "digest"))

MANIFESTS_REPO_NAME = "manifests"

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

def _get_repo_url(repo_spec):
  """Get a tuple representing the resource URL.

  Args:
   repo_spec: Dictionary for the repo spec

  Returns:
    tuple representing the git url
  """
  url = _get_param(repo_spec["resourceSpec"]["params"], "url")

  if not url:
    raise ValueError(f"Repository {r['name']} is missing param url") # pylint: disable=syntax-error

  url = url["value"]
  repo = _parse_git_url(url)
  return repo

def _sync_repos(repos, src_dir):
  """Make sure all the repositories are checked out to src dir and up to date."""

  if not os.path.exists(src_dir):
    os.makedirs(src_dir)

  for r in repos:
    repo = _get_repo_url(r)

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

  # Add some helpful labels
  # This will be used to see if we already have a pipeline running for
  # a specific application and version
  if not "labels" in app_run["metadata"]:
    app_run["metadata"]["labels"] = {}
  app_run["metadata"]["labels"]["app"] = app["name"]
  app_run["metadata"]["labels"]["version"] = version["name"]
  app_run["metadata"]["labels"]["image_tag"] = tag

  return app_run


def _deep_copy(data):
  value = yaml.dump(data)
  return yaml.load(value)


def _get_image(config, image_name):
  """Get the tag for an image

  Args:
    config: kustomization config
    image_name: Name of the image
  """
  for i in config.get("images"):
    if i["name"] == image_name:
      image_name = i.get("newName", image_name)

      new_tag = i.get("newTag", "")

      if not new_tag:
        if ":" in image_name:
          image_name, new_tag = image_name.split(":", 1)

      new_digest = i.get("digest", "")

      return IMAGE_TUPLE(image_name, new_tag, new_digest)

  raise LookupError(f"Could not find image: {image_name}")

def _handle_app(run, app, version, src_dir, output_dir):
  """Create the PipelineRun for the specified application.

  Returns:
    run_file: The file containing the PipelineRun
    needs_update: (boolean) True if the kustomize manifest is outdated and
      we need to run the pipeline to update it
  """
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

  manifests_branch = _get_param(app_version.manifests_repo["resourceSpec"]
                                ["params"], "revision")["value"]


  manifests_repo = _get_repo_url(app_version.manifests_repo)

  manifests_dir = os.path.join(src_dir, manifests_repo.owner,
                               manifests_repo.repo)
  util.run(["git", "checkout", f"origin/{manifests_branch}"],
           cwd=manifests_dir)

  # Determine whether the application/version actually needs to be run or not
  # We do this by loading the kustomize file and seeing if it is up to date
  path_to_manifests_dir = _get_param(app["params"],
                                     "path_to_manifests_dir")["value"]
  kustomization_path = os.path.join(manifests_dir,
                                    path_to_manifests_dir,
                                    "kustomization.yaml")

  with open(kustomization_path) as hf:
    kustomize_config = yaml.load(hf)

  src_image_url = _get_param(app["params"], "src_image_url")["value"]

  current_image = _get_image(kustomize_config, src_image_url)

  logging.info(f"App: {app['name']} Version: {version['name']} "
               f"Current Image Tag: {current_image.tag}")

  needs_update = False
  if current_image.tag != run["metadata"]["labels"]["image_tag"]:
    needs_update = True
    logging.info(f"App: {app['name']} Version: {version['name']} "
                 f"needs to be updated to tag {current_image.tag}")

  return output_file, needs_update

class UpdateKfApps:

  @staticmethod
  def create_runs(config, output_dir, template, src_dir):
    """Create YAML files for the pipeline runs.

    Args:
      config: The path to the configuration
      output_dir: Directory where pipeline runs should be written
      template: The path to the YAML file to act as a template
      src_dir: Directory where source should be checked out
    """

    with open(config) as hf:
      run_config = yaml.load(hf)

    failures = []

    # List of the YAML files corresponding to pipeline runs that need to
    # be run.
    all_pipelines = []
    pipelines_to_run = []

    # Loop over the cross product of versions and applications and generate
    # a run for each one.
    for version in run_config["versions"]:
      _sync_repos(version["repos"], src_dir)

      for app in run_config["applications"]:
        pair = APP_VERSION_TUPLE(app["name"], version["name"])
        # Load a fresh copy of the template
        with open(template) as hf:
          run = yaml.load(hf)


        # Make copies of app and version so that we don't end up modifying them
        try:
          run_file, needs_update = _handle_app(run, _deep_copy(app),
                                               _deep_copy(version),
                                               src_dir, output_dir)

          all_pipelines.append(run_file)
          if needs_update:
            pipelines_to_run.append(run_file)
        except (ValueError, LookupError) as e:
          failures.append(pair)
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

    logging.info(f"Pipelines that need to be run {len(pipelines_to_run)} of "
                 f"{len(all_pipelines)}")
    logging.info("The pipelines that need to be run are:\n%s","\n".join(
      pipelines_to_run))

    return all_pipelines, pipelines_to_run

  @staticmethod
  def apply(config, output_dir, template, src_dir, namespace):
    """Create PipelineRuns for any applications that need to be updated."""

    k8s_config.load_kube_config(persist_config=False)

    client = k8s_client.ApiClient()
    crd_api = k8s_client.CustomObjectsApi(client)

    _, pipelines_to_run = UpdateKfApps.create_runs(
      config, output_dir, template, src_dir)

    if not pipelines_to_run:
      logging.info("No pipelines need to be run")
      return

    #pipelines_to_run = ["/tmp/runs/admission-webhook-run-master-6b987df8.yaml",
                        #"/tmp/runs/kfam-run-master-caf5eb33.yaml"]
    for p in pipelines_to_run:
      with open(p) as hf:
        run = yaml.load(hf)

      group, version = run["apiVersion"].split("/", 1)
      kind = run["kind"]
      plural = kind.lower() + "s"

      # Check if there are any pipelines running for the same application
      label_filter = {}
      for k in ["app", "version", "image_tag"]:
        label_filter[k] = run["metadata"]["labels"][k]

      items = [f"{k}={v}" for k,v in label_filter.items()]
      selector = ",".join(items)

      current_runs = crd_api.list_namespaced_custom_object(
        group, version, namespace, plural, label_selector=selector)

      active_run = None
      for r in current_runs["items"]:
        conditions = r["status"].get("conditions", [])

        running = True

        for c in conditions[::-1]:
          if c.get("type", "").lower() == "succeeded":
            if c.get("status", "").lower() in ["true", "false"]:
              running = False
            break

        if running:
          active_run = r['metadata']['name']
          break

      if active_run:
        logging.info(f"Found pipeline run {active_run} "
                     f"already running for {p}; not rerunning")
        continue

      logging.info(f"Creating run from file {p}")
      result = crd_api.create_namespaced_custom_object(group, version, namespace, plural,
                                                       run)
      logging.info(f"Created run {result['metadata']['name']}")


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
    self.manifests_repo = None

    for r in version["repos"]:
      if r["name"] == app["sourceRepo"]:
        self.source_repo = r
      if r["name"] == MANIFESTS_REPO_NAME:
        self.manifests_repo = r

    if not self.source_repo:
      raise ValueError(f"App {app['name']} uses repo {app['sourceRepo']} "
                       f"but this repo was not defined in version "
                       f"{version['name']}")


    if not self.manifests_repo:
      raise ValueError(f"Repo {MANIFESTS_REPO_NAME} was not defined in version "
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
