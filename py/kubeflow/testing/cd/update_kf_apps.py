"""A python script to run Tekton pipelines to update Kubeflow manifests."""

# TODO(jlewi): We might want to emit structured logs and then sync to
# BigQuery to support easy monitoring.

import fire
import collections
import logging
import os
import subprocess
import traceback
import re
import time
import yaml

from kubeflow.testing import kf_logging
from kubeflow.testing import util
from kubeflow.testing import yaml_util
from kubeflow.testing.cd import close_old_prs
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

GIT_URL_RE = re.compile(r"([^:]*):([^/]*)/([^\.]*)\.git")

GIT_TUPLE = collections.namedtuple("git_tuple", ("host", "owner", "repo"))

APP_VERSION_TUPLE = collections.namedtuple("app_version", ("app", "version"))

IMAGE_TUPLE = collections.namedtuple("image", ("name", "tag", "digest"))

PR_INFO = collections.namedtuple("pr_info", ("url", "author", "branch"))

MANIFESTS_REPO_NAME = "manifests"

# The name of the GitHub user under which kubeflow-bot branches exist
KUBEFLOW_BOT = "kubeflow-bot"

# The name of the git resource in the Tekton pipeline that will be the
# git resource containing the application source code.
APP_REPO_RESOURCE_NAME = "app-repo"

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
    raise ValueError(f"Repository {repo_spec['name']} is missing param url") # pylint: disable=syntax-error

  url = url["value"]
  repo = _parse_git_url(url)
  return repo

def _sync_repos(repos, src_dir):
  """Make sure all the repositories are checked out to src dir and up to date."""

  if not os.path.exists(src_dir):
    os.makedirs(src_dir)

  for r in repos:
    repo = _get_repo_url(r)

    # Convert the repo to https so we don't need ssh keys; this is a bit
    # of a hack.
    url = f"https://github.com/{repo.owner}/{repo.repo}.git"

    logging.info(f"Sync mapped repo {r} to {url}")

    repo_dir = os.path.join(src_dir, repo.owner, repo.repo)
    if not os.path.exists(repo_dir):
      if not os.path.exists(os.path.join(src_dir, repo.owner)):
        os.makedirs(os.path.join(src_dir, repo.owner))
      logging.info(f"Clone {url}")
      util.run(["git", "clone", url, repo.repo],
               cwd=os.path.join(src_dir, repo.owner))

    logging.info(f"Sync repo {repo}")

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
    path: The relative path; if none or empty run in the root of the repo
  """
  util.run(["git", "checkout", branch], cwd=repo_root)
  command = ["git", "log", "-n", "1", "--pretty=format:\"%h\""]
  if path:
    command.append(path)
  output = util.run(command, cwd=repo_root)

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
  # Before we override the repositories we need to change the name of the
  # repo containing the source to be the name of the parameter
  # APP_REPO_RESOURCE_NAME
  source_index = _param_index(version["repos"], app["sourceRepo"])
  version["repos"][source_index]["name"] = APP_REPO_RESOURCE_NAME

  # Tekton will give us an error if we include extra resources; i.e. resources
  # not defined in the Pipeline spec. So we need to remove from version all
  # the repos we don't need
  expected_repos = [APP_REPO_RESOURCE_NAME, "manifests", "ci-tools"]

  new_repos = []
  for v in version["repos"]:
    if v["name"] in expected_repos:
      new_repos.append(v)

  version["repos"] = new_repos

  app_run["spec"]["resources"] = _combine_params(app_run["spec"]["resources"],
                                                 version["repos"])

  # Override the commit for the src repo to pin to a specific commit
  source_index = _param_index(app_run["spec"]["resources"],
                              APP_REPO_RESOURCE_NAME)
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

def _open_prs(repo_dir):
  """Return open PRs for the given repository.

  Args:
    repo_dir: The directory for the repo to list open PRs for.

  Returns:
    prs: [PR_INFO]; list of PR_INFO objects describing open PRs
  """
  # See hub conventions:
  # https://hub.github.com/hub.1.html
  # The GitHub repository is determined automatically based on the name
  # of remote repositories
  #
  # Don't use util.run because we don't want to echo output of hub pr
  output = subprocess.check_output(["hub", "pr", "list", "--format=%U;%H;%t\n"],
                                   cwd=repo_dir).decode()


  lines = output.splitlines()

  prs = []
  for l in lines:
    pieces = l.split(";")

    # Title could potentially have semi colons in it so we could wind up
    # with more than 3 pieces.
    if len(pieces) < 3:
      logging.error(f"Line {l} doesn't appear to match expected format of "
                    f"url;head;title")
      continue
    url = pieces[0]
    head = pieces[1]
    # The head reference of the PRis in the format {author}:{branch}
    head_pieces = head.split(":")
    if len(head_pieces) != 2:
      logging.error(f"Head={head} doesn't appear to be in form $author:$branch")
      continue
    author = head_pieces[0]
    branch = head_pieces[1]
    prs.append(PR_INFO(url, author, branch))

  return prs

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
    # We want to allow it to be the root of the repository
    src_path = ""
    logging.info("src_path not specified or is root of repository")


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
               f"{version['name']} to file {output_file}",
               extra=run["metadata"]["labels"])
  with open(output_file, "w") as hf:
    yaml.dump(run, hf)

  manifests_branch = _get_param(app_version.manifests_repo["resourceSpec"]
                                ["params"], "revision")["value"]


  manifests_repo = _get_repo_url(app_version.manifests_repo)

  manifests_dir = os.path.join(src_dir, manifests_repo.owner,
                               manifests_repo.repo)
  util.run(["git", "checkout", f"origin/{manifests_branch}"],
           cwd=manifests_dir)

  # Determine whether there is already a PR open to update the image.
  #
  # We do this by looking to see if there is a PR open for the branch that
  # a PR would create.
  image_tag = run["metadata"]["labels"]["image_tag"]
  pr_branch = _branch_for_app(app, image_tag)

  open_prs = _open_prs(manifests_dir)

  logging.info(f"Checking if there is a PR from {KUBEFLOW_BOT} "
               f"for branch {pr_branch}")

  for pr in open_prs:
    if pr.branch == pr_branch:
      logging.info(f"For App: {app['name']} Tag: {image_tag} found "
                   f"open PR {pr.url}")

      return output_file, False

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

def _branch_for_app(app, image_tag):
  """Return the branch that will be used to update the specified application.

  Args:
    app: Dictionary describing the app.
    image_tag: The tag for image
  """

  # This logic needs to match what the script creating the PR is doing.
  # e.g.
  # https://github.com/kubeflow/testing/blob/909454ab283d6ee67107a1c1607ca4ec9542bfeb/py/kubeflow/testing/ci/rebuild-manifests.sh#L47
  src_image_url = _get_param(app["params"], "src_image_url")["value"]

  image_name = src_image_url.split("/")[-1]
  return f"update_{image_name}_{image_tag}"

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

    run_config = yaml_util.load_file(config)

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
        run = yaml_util.load_file(template)

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
          extra = {
            "app": app['name'],
            "version": version['name'],
          }
          logging.error(f"Exception occured creating run for "
                        f"App: {app['name']} Version: {version['name']} "
                        f"Exception: {e}\n"
                        f"{traceback.format_exc()}\n.", extra=extra)

    if failures:
      failed = [f"(App:{i.app}, Version:{i.version})" for i in failures]
      failed = ", ".join(failed)
      logging.error(f"Failed to generate pipeline runs for: {failed}")
    else:
      logging.info("Succcessfully created pipeline runs for all apps and "
                   "versions")

    logging.info(f"Pipelines that need to be run {len(pipelines_to_run)} of "
                 f"{len(all_pipelines)}")
    logging.info("The pipelines that need to be run are:\n%s", "\n".join(
      pipelines_to_run))

    return all_pipelines, pipelines_to_run

  @staticmethod
  def apply(config, output_dir, template, src_dir, namespace):
    """Create PipelineRuns for any applications that need to be updated.

    Args:
      config: The path to the configuration; can be local or http file
      output_dir: Directory where pipeline runs should be written
      template: The path to the YAML file to act as a template
      src_dir: Directory where source should be checked out
    """

    logging.info("Closing old PRs")
    closer = close_old_prs.PRCloser()
    closer.apply()

    service_account_path = "/var/run/secrets/kubernetes.io"
    if os.path.exists("/var/run/secrets/kubernetes.io"):
      logging.info(f"{service_account_path} exists; loading in cluster config")
      k8s_config.load_incluster_config()
    else:
      logging.info(f"{service_account_path} doesn't exists; "
                    "loading kube config file")
      k8s_config.load_kube_config(persist_config=False)

    client = k8s_client.ApiClient()
    crd_api = k8s_client.CustomObjectsApi(client)

    _, pipelines_to_run = UpdateKfApps.create_runs(
      config, output_dir, template, src_dir)

    if not pipelines_to_run: # pylint: disable=too-many-nested-blocks
      logging.info("No pipelines need to be run")
    else:
      logging.info("Submitting pipeline runs to update applications")
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

        items = [f"{k}={v}" for k, v in label_filter.items()]
        selector = ",".join(items)

        # TODO(https://github.com/tektoncd/pipeline/issues/1302): We should
        # probably do some garbage collection of old runs.
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

        labels = run["metadata"]["labels"]
        if active_run:
          logging.info(f"Found pipeline run {active_run} "
                       f"already running for {p}; not rerunning",
                       extra=labels)
          continue

        logging.info(f"Creating run from file {p}", extra=labels)
        result = crd_api.create_namespaced_custom_object(group, version, namespace, plural,
                                                         run)
        logging.info(f"Created run "
                     f"{result['metadata']['namespace']}"
                     f".{result['metadata']['name']}", extra=labels)


  @staticmethod
  def sync(config, output_dir, template, src_dir, namespace,
           sync_time_seconds=600):
    """Perioridically fire off tekton pipelines to update the manifests.

    Args:
      config: The path to the configuration
      output_dir: Directory where pipeline runs should be written
      template: The path to the YAML file to act as a template
      src_dir: Directory where source should be checked out
      sync_time_seconds: Time in seconds to wait between launches.
    """
    while True:
      UpdateKfApps.apply(config, output_dir, template, src_dir, namespace)
      logging.info("Wait before rerunning")
      time.sleep(sync_time_seconds)

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
  # Emit logs in json format. This way we can do structured logging
  # and we can query extra fields easily in stackdriver and bigquery.
  json_handler = logging.StreamHandler()
  json_handler.setFormatter(kf_logging.CustomisedJSONFormatter())

  logger = logging.getLogger()
  logger.addHandler(json_handler)
  logger.setLevel(logging.INFO)

  fire.Fire(UpdateKfApps)
