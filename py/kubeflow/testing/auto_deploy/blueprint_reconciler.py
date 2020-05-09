"""The reconciler for auto deployed blueprints.

The reconciler is responsible for launching Tekton PipelineRuns to
deploy the blueprint and garbage collecting old instances

Thid is the legacy versions which:
  1. Doesn't support blueprints (i.e. uses Deployment Manager)
  2. Uses K8s jobs not Tekton PipelineRuns.
"""
import collections
import datetime
from dateutil import parser as date_parser
import fire
import logging
import os
import re
import time
import uuid
import yaml

from kubeflow.testing import cnrm_clients
from kubeflow.testing.auto_deploy import util as auto_deploy_util
from kubeflow.testing import cleanup_blueprints
from kubeflow.testing import delete_kf_instance
from kubeflow.testing import gcp_util
from kubeflow.testing import git_repo_manager
from kubeflow.testing import kf_logging
from kubeflow.testing import tekton_cr_clients
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client import rest

# The minimum time to wait before triggering another deployment.
MIN_TIME_BETWEEN_DEPLOYMENTS = datetime.timedelta(minutes=20)

# The maximum number of active deployments
# TODO(jlewi): Maybe bump this later on.
MAX_ACTIVE_DEPLOYMENTS = 10

# Durations related to GC
# Minimum amount of time to leave a deployment up before it is eligble for
# deletion. Try to avoid deleting clusters from underneath people and
# tests. We need to leave enough time for any tests running on the cluster
# to finish. Assume 1 hour to setup KF, 1 hour to run tests, 1 hour of buffer
MIN_LIFETIME = datetime.timedelta(hours=3)

# How old must be the next most recent deployment before a given deployment
# is deleted. i.e. if x is older than y then before we delete x we want
# y to be old enough to assume that people have moved over y rather than use
# x
GRACE_PERIOD = datetime.timedelta(hours=3)

# We want to periodically redeploy even if the version hasn't changed
PERIODIC_REDEPLOY = datetime.timedelta(hours=12)

# TODO(jlewi): We shouldn't hardcode this.
NAMESPACE = "kubeflow-ci-deployment"

def _pipeline_is_running(j):
  """Return true if the specified K8s job is still running.

  Args:
    j: A K8s job object
  """
  conditions = j.get("status", {}).get("conditions", [])

  if not conditions:
    return True

  for c in conditions[::-1]:
    # It looks like when a pipelinerun fails we have condition succceeded
    # and status False
    if c["type"].lower() in ["succeeded", "failed", "complete"]:
      return False

  return True

# Name of the blueprints repo parameter
BLUEPRINTS_REPO = "blueprint-repo"
GROUP_LABEL = "auto-deploy-group"
BASE_NAME_LABEL = "auto-deploy-base-name"
UNKNOWN_GROUP = "unknown"

BLUEPRINT_COMMIT_LABEL = "blueprint-repo-commit"

class NotAPipeline(Exception):
  pass

class PipelineRunWrapper:
  """A container to keep track of the various pipeline runs to use."""
  def __init__(self, resource):
    """
    Args:
      resource: A dictionary representing the K8s PipelineRun
    """
    self.resource = resource

  @staticmethod
  def from_file(file_path):
    with open(file_path) as hf:
      resource = yaml.load(hf)

      if resource.get("kind", "") != "PipelineRun":
        raise NotAPipeline

    missing = []
    for l in [GROUP_LABEL, BASE_NAME_LABEL]:
      if not l in resource["metadata"]["labels"]:
        missing.append(l)

    if missing:
      labels = ",".join(missing)
      raise ValueError(f"PipelineRun in {file_path} is missing labels "
                       f"{labels}")

    return PipelineRunWrapper(resource)

  @property
  def base_name(self):
    """Return the name to use for this deployment."""
    return self.resource["metadata"]["labels"][BASE_NAME_LABEL]

  @property
  def group(self):
    return self.resource["metadata"]["labels"][GROUP_LABEL]

  def get_resource_param(self, resource_name, param_name):
    """Return the value of the specified parameter or none"""

    for resource in self.resource["spec"].get("resources", []):
      if resource["name"] != resource_name:
        continue
      for param in resource["resourceSpec"].get("params", []):
        if param["name"] == param_name:
          return param["value"]

    return None

  def set_resource_param(self, resource_name, name, value):
    """Set the parameter."""

    for resource in self.resource["spec"].get("resources", []):
      if resource["name"] != resource_name:
        continue

      for param in resource["resourceSpec"].get("params", []):
        if param["name"] == name:
          param["value"] = value
          return

      if not "params" in resource["resourceSpec"]:
        resource["resourceSpec"]["params"] = {}

      resource["resourceSpec"]["params"].append({
        "name": name,
        "value": value,
      })
      return

    raise ValueError(f"Missing resource {resource_name}")

  def get_param(self, name):
    """Get the parameter or none if not set"""
    for param in self.resource["spec"].get("params", []):
      if param["name"] == name:
        return param["value"]
    return None

  def set_param(self, name, value):
    """Set the parameter."""

    for param in self.resource["spec"].get("params", []):
      if param["name"] == name:
        param["value"] = value
        return

    if not "params" in self.resource["spec"]:
      self.resource["spec"]["params"] = []

    self.resource["spec"]["params"].append({
      "name": name,
      "value": value,
    })

  def copy(self):
    # Make a deep copy by serializing and deserializing it.
    return PipelineRunWrapper(yaml.load(yaml.dump(self.resource)))

def labels_to_selector(labels):
  pairs = []
  for k,v in labels.items():
    pairs.append(f"{k}=v")
  return ",".join(pairs)

class AutoDeployedBlueprint:
  def __init__(self, cluster):
    """Create an object to represent an AutoDeployed instance.

    Args:
      cluster: Dictionary representing a containercluster CNRM object
       corresponding to the blueprint
    """
    self.cluster = cluster

    self.create_time = date_parser.parse(self.cluster["metadata"].get(
      "creationTimestamp"))

  @property
  def name(self):
    return self.cluster["metadata"]["name"]

  @property
  def commit(self):
    """The commit of the blueprint.

    Returns None if the commit is unknown.
    """
    return self.cluster["metadata"]["labels"].get(BLUEPRINT_COMMIT_LABEL,
                                                  None)

class BlueprintReconciler: # pylint: disable=too-many-instance-attributes
  def __init__(self, pipeline_runs, local_dir=None,
               management_context=None, tekton_context=None,
               deployments_dir=None):
    """Construct a reconciler

    Args:
      pipeline_runs: List of PipelineRunWrapper.
      management_context: The kubernetes context for the management cluster used
        with blueprints
      tekton_context: The kubernetes context for submitting Tekton runs.
    """
    # This is a map:
    # The value of the GROUP label to -> List of deployments
    self._deployments = None

    # A list of PipelineRunWrapper objects
    self._pipeline_runs = pipeline_runs

    # A map from GitUrls to GitRepoManager managing that repo URL
    # to the GitRepoManager.
    self._manifests_repo = {}

    # Logging context. A dictionary of extra labels for logs
    self._log_context = {}

    # If provided this should be a multiprocessing queue on which to
    # push info about deployments
    self._queue = None

    # Directory where YAML files listing deployments should be written.
    # This is used to make it available to other processes
    self._deployments_dir = deployments_dir

    self._manifests_client = None

    self._local_dir = local_dir
    self._management_context = management_context
    self._tekton_context = tekton_context
    self._tekton_api = None
    self._management_api = None

  @property
  def management_api(self):
    if not self._management_api:
      k8s_config.load_kube_config(persist_config=False,
                                  context=self._management_context)
      self._management_api = k8s_client.ApiClient()
    return self._management_api

  @property
  def tekton_api(self):
    if not self._tekton_api:
      k8s_config.load_kube_config(persist_config=False,
                                  context=self._tekton_context)
      self._tekton_api = k8s_client.ApiClient()
    return self._tekton_api

  @staticmethod
  def from_pipelines_dir(pipelines_dir, tekton_context=None,
                         management_context=None, **kwargs):
    """Construct a reconciler from the config path.

    Args:
      pipelines_dir: Directory containing YAML files with Tekton PipelineRuns
      **kwargs: Additional constructor arguments see __init__.
    """

    pipeline_runs = []
    for root, _, files in os.walk(pipelines_dir, topdown=False):
      for f in files:
        full_path = os.path.join(root, f)
        if not f.endswith(".yaml"):
          logging.info(f"Skipping file {full_path}")
          continue

        try:
          pipeline_runs.append(PipelineRunWrapper.from_file(full_path))
        except NotAPipeline:
          logging.info(f"Skipping file {full_path}; does not contain a "
                       f"PipelineRun")

    if not pipeline_runs:
      raise ValueError(f"No pipelineruns loaded from directory {pipelines_dir}")

    reconciler = BlueprintReconciler(pipeline_runs=pipeline_runs,
                                     management_context=management_context,
                                     tekton_context=tekton_context,
                                     **kwargs)

    logging.info(f"Using deployments directory={reconciler._deployments_dir}") # pylint: disable=protected-access

    return reconciler


  def _save_deployments(self):
    if not self._deployments_dir:
      logging.info("No deployments directory provided; not persisting "
                   "deployments")
      return
    # Write the deployments to a file in order to make them
    # available to all the flask threads and processes
    suffix = datetime.datetime.now().strftime("%y%m%d-%H%M%S")

    if not os.path.exists(self._deployments_dir):
      os.makedirs(self._deployments_dir)

    d = {}
    for k, v in self._deployments.items():
      d[k] = [i.cluster for i in v]

    path = os.path.join(self._deployments_dir, f"clusters.{suffix}.yaml")

    logging.info(f"Writing clusters to {path}")
    with open(path, "w") as hf:
      yaml.dump(d, hf)

    # TODO(jlewi): We should GC old versions of the file.

  def _iter_blueprints(self):
    """Return an iterator over blueprints.

    Args:
      namespace: The namespace to look for blueprints
      context: The kube context to use.
    """
    # We need to load the kube config so that we can have credentials to
    # talk to the APIServer.
    crd_api = cnrm_clients.CnrmClientApi(self.management_api, "containercluster")

    # Treat all clusters with an auto-group-label as an auto deployed group.
    selector = GROUP_LABEL
    namespace = "kubeflow-ci-deployment"
    # TODO(jlewi): We should get namespaces by looking at the PipelineRuns
    # to get the project it is deployed to.
    logging.warning(f"Using hardcoded value of namespace={namespace} to look "
                    f"for deployments.")
    clusters = crd_api.list_namespaced(namespace, label_selector=selector)

    for c in clusters.get("items"):
      yield c

  def _get_deployments(self):
    """Build a map of all auto deployments

    Args:
      deployments: (Optional) Iterator over GCP deployments.
    """
    logging.info("Building map of auto deployments")

    clusters = self._iter_blueprints()

    self._deployments = collections.defaultdict(lambda: [])

    for c in clusters:
      name = c["metadata"]["name"]
      labels = c["metadata"]["labels"]

      # Tha name of blueprint
      kf_name = c["metadata"].get("labels", {}).get(cleanup_blueprints.NAME_LABEL, "")

      auto_deploy_group = labels.get(GROUP_LABEL, UNKNOWN_GROUP)

      if auto_deploy_group == UNKNOWN_GROUP:
        logging.warning(f"Cluster {name} missing label {GROUP_LABEL}; "
                         f"assigning it to group {UNKNOWN_GROUP}")

      if kf_name != name:
        # TODO(jlewi): This shouldn't be happening. Hopefully this was just
        # temporary issue with the first couple of auto-deployed clusters I
        # created and we can delete this code.
        logging.error("Found cluster named:%s with label kf-name: %s. The name "
                      "will be used. This shouldn't happen. This hopefully "
                      "was just due to a temporary bug in the early versions "
                      "of create_kf_from_gcp_blueprint.py that should be fixed "
                      "so it shouldn't be happening in new instances anymore."
                      , name, kf_name)
        kf_name = name

      context = {
        "deployment_name" : kf_name,
        GROUP_LABEL : auto_deploy_group,
      }

      create_time = date_parser.parse(c["metadata"].get("creationTimestamp"))

      blueprint = AutoDeployedBlueprint(c)
      logging.info(f"Found blueprint={name} in Group={auto_deploy_group}",
                   extra=context)
      self._deployments[auto_deploy_group] = (self._deployments[auto_deploy_group] +
                                              [blueprint])

    # Sort the values by timestamp
    branches = self._deployments.keys()
    for b in branches:
      self._deployments[b] = sorted(self._deployments[b],
                                    key=lambda x: x.create_time)

    self._save_deployments()

  def _launch_pipeline(self, run, commit):
    """Launch a K8s job to deploy Kubeflow.

    Args:
      run: Dictionary representing the pipelinerun to launch
      commit: The commit to launch from.
    """

    # Don't want to modify the original pipelinerun
    run = run.copy()

    run.set_resource_param(BLUEPRINTS_REPO, "revision", commit)

    # Kubeflow deployment name
    # We need to keep the name short to avoid hitting limits with certificates.
    uid = datetime.datetime.now().strftime("%m%d") + "-"
    uid = uid + uuid.uuid4().hex[0:3]
    kf_name = f"{run.base_name}-{uid}"

    run.set_param("name", kf_name)

    # TODO(jlewi): Can we just specify this in the configs?
    if os.getenv("JOB_NAMESPACE"):
      namespace = os.getenv("JOB_NAMESPACE")
      logging.info(f"Setting job namespace to {namespace}",
                   extra=self._log_context)
      run.resource["metadata"]["namespace"] = namespace

    namespace = run.resource["metadata"]["namespace"]

    # Check if there is already a running job
    label_filter = {
      GROUP_LABEL: run.group,
      BLUEPRINT_COMMIT_LABEL: commit,
    }

    items = [f"{k}={v}" for k, v in label_filter.items()]
    selector = ",".join(items)

    api_client = self.tekton_api

    runs_client = tekton_cr_clients.TektonClientApi(
      api_client, "PipelineRun")
    runs = runs_client.list_namespaced(namespace, label_selector=selector)

    if runs.items:
      for j in runs["items"]:
        logging.info(f"Found PipelineRun {j['metadata']['name']}",
                     extra=self._log_context)

        if _pipeline_is_running(j):
          logging.info(
            f"PipelineRun {j['metadata']['name']} is still running; not launching "
            f"a new job",
            extra=self._log_context)
          return

    # TODO(jlewi): How should we set the name of the KF deployment?
    # By default it would be generated at runtime by
    # create_kf_from_gcp_blueprint but we don't want to do that because
    # then we can't attach labels to the pipelineRun that make it easy
    # to map PipelineRuns to specific deployments. We should probably
    # set the name parameter in the PipelineRun. We can then add a
    # label "kf-name" to store the name
    labels = {
      cleanup_blueprints.NAME_LABEL: kf_name
    }

    labels.update(label_filter)

    run.resource["metadata"]["labels"].update(labels)

    run.set_resource_param("blueprint-repo", "revision", commit)
    # TODO(jlewi): Handle errors
    try:

      new_run = runs_client.create_namespaced(namespace, run.resource)
      full_name = f"{namespace}.{new_run['metadata']['name']}"
      logging.info(f"Submitted PipelineRun {full_name}",
                   extra=self._log_context)

    except rest.ApiException as e:  # pylint: disable=unused-variable
      logging.error(f"Could not submit PipleineRun for deployment "
                    f"{run.name} :\n{e}", extra=self._log_context)


  def _delete_blueprint(self, labels):
    """Delete a blueprint.

    Deletes a blueprint by deleting all CNRM resources a set of labels.

    We use labels because all objects belonging to a blueprint should have
    the same label but the names might vary.
    """
    kinds = ["containercluster", "iampolicymember",
             "iamserviceaccount", "containernodepool",
             "computeaddress", "computedisk"]

    api_client = self.management_api
    for kind in kinds:
      client = cnrm_clients.CnrmClientApi(api_client, kind)
      selector = labels_to_selector(labels)

      logging.warning(f"Using hardcoded namespace {NAMESPACE}",
                      extra=self._log_context)
      results = client.list_namespaced(NAMESPACE)

      if not results.items:
        logging.info(f"No resources of kind {kind} found to delete for "
                     f"selector {selector}", extra=self._log_context)

      for i in results["items"]:
        name = i["metadata"]["name"]
        logging.info(f"Deleting kind: {kind} {NAMESPACE}.{name}",
                     extra=self._log_context)
        client.delete_namespaced(NAMESPACE, name, {})


  def _gc_deployments(self):
    """Delete old deployments"""
    kf_deleter = delete_kf_instance.KFDeleter()

    for group, blueprints in self._deployments.items():
      self._log_context = {
        GROUP_LABEL: group,
      }

      logging.info(f"Group {group} has {len(blueprints)} active deployments",
                   extra=self._log_context)

      # We want at least one deployment for each version
      if len(blueprints) <= 1:
        continue

      # deployments should already be sorted by create time.
      # we always want to keep at least 1 deployment so we never delete
      # the last deployment
      for index, d in enumerate(blueprints[:-1]):
        now = datetime.datetime.now(d.create_time.tzinfo)
        age = now - d.create_time

        self._log_context[cleanup_blueprints.NAME_LABEL] = d.name
        if age < MIN_LIFETIME:
          logging.info(f"Deployment {d.name} not eligible for deletion; "
                       f"It is only {age} old", extra=self._log_context)
          # Since all the other deployments will be younger none of them
          # will be eligible
          break

        # Make sure the next deployment is at least older than the GRACE_PERIOD
        # before deleting this one.
        next_oldest = blueprints[index + 1]
        now = datetime.datetime.now(next_oldest.create_time.tzinfo)
        next_age = now - next_oldest.create_time

        if next_age < GRACE_PERIOD:
          logging.info(f"Deployment {d.name} not eligible for deletion; "
                       f"The next oldest deployment "
                       f"{next_oldest.name} is only "
                       f"{next_age}(HH:MM:SS) old",
                       extra=self._log_context)
          break

        logging.info(f"Deleting deployment {d.name}; age={age} "
                     f"create_time={d.create_time}", extra=self._log_context)


        labels = {
          cleanup_blueprints.NAME_LABEL: d.name,
        }
        self._delete_blueprint(labels)

  def _reconcile(self):
    # Get the deployments.
    self._get_deployments()

    # Compute the current number of deployments
    active_deployments = 0
    for _, i in self._deployments.items():
      active_deployments += len(i)


    for run in self._pipeline_runs:
      self._log_context = {
        GROUP_LABEL: run.group,
      }
      logging.info(f"Reconciling pipeline group: {run.group}",
                   extra=self._log_context)

      branch = run.get_resource_param(BLUEPRINTS_REPO, "revision")
      git_url = run.get_resource_param(BLUEPRINTS_REPO, "url")

      if not git_url in self._manifests_repo:
        pattern = re.compile("https://[^/]*/([^/]*)/([^#]*).git")
        match = pattern.match(git_url)
        if not match:
          raise ValueError(f"Repo url {git_url} did not patch regex: "
                           f" {pattern.pattern}")
        local_dir = os.path.join(self._local_dir, match.group(1),
                                 match.group(2))
        self._manifests_repo[git_url] = git_repo_manager.GitRepoManager(
          url=git_url, local_dir=local_dir)

      repo = self._manifests_repo[git_url]

      full_branch = f"{repo.remote_name}/{branch}"

      # Sync the repositories because we use this to find the latest changes.
      repo.fetch()
      last_commit = repo.last_commit(full_branch, "")
      logging.info(f"Last commit to group={run.group} "
                   f"commit={last_commit}", extra=self._log_context)

      # Get the commit of the last deployment for this version
      if self._deployments[run.group]:
        last_deployed = self._deployments[run.group][-1]

        now = datetime.datetime.now(tz=last_deployed.create_time.tzinfo)
        time_since_last_deploy = now - last_deployed.create_time

        logging.info(f"group={run.group} "
                     f"last_commit={last_commit} most recent "
                     f"deployment is {last_deployed.name} "
                     f"at commit={last_deployed.commit} "
                     f"age={time_since_last_deploy}",
                     extra=self._log_context)

        if (last_deployed.commit == last_commit and
            time_since_last_deploy < PERIODIC_REDEPLOY):
          logging.info(f"group={run.group} no sync needed",
                       extra=self._log_context)
          continue

        logging.info(f"group={run.group} sync needed",
                     extra=self._log_context)

        if time_since_last_deploy < MIN_TIME_BETWEEN_DEPLOYMENTS:
          minutes = time_since_last_deploy.total_seconds() / 60.0
          logging.info(f"group={run.group} can't start a new deployment "
                       f"because deployment for {last_deployed.deployment_name }"
                       f"is only {minutes} minutes old", extra=self._log_context)
          continue
      else:
        logging.info(f"group={run.group} has no active deployments",
                     extra=self._log_context)

      if active_deployments >= MAX_ACTIVE_DEPLOYMENTS:
        logging.info(f"group={run.group} can't start a new deployment "
                     f"there are currently {active_deployments} active "
                     f"deployments already.", extra=self._log_context)
        continue

      self._launch_pipeline(run, last_commit)

    # TODO(jlewi): We should GC the older deployments. We should have
    # some min TTL so we don't delete clusters from underneath people.
    # We should then GC any clusters as long as there as a newer cluster
    # already available. We should require that the new cluster is at least
    # 30 minutes old so that we know its ready.
    self._gc_deployments()

  def run(self, period=datetime.timedelta(minutes=5)):
    """Continuously reconcile."""

    # Ensure we can get GCP credentials
    if not gcp_util.get_gcp_credentials():
      raise RuntimeError("Could not get GCP application default credentials")

    while True:
      self._reconcile()
      logging.info(f"Wait {period}(HH:MM:SS) before reconciling; ")
      time.sleep(period.total_seconds())

class CLI:
  @staticmethod
  def run(pipelines_dir, deployments_dir, local_dir=None,
          tekton_context=None, management_context=None):
    reconciler = BlueprintReconciler.from_pipelines_dir(
        pipelines_dir, deployments_dir=deployments_dir, local_dir=local_dir,
        management_context=management_context, tekton_context=tekton_context)
    reconciler.run()

if __name__ == "__main__":
  # Emit logs in json format. This way we can do structured logging
  # and we can query extra fields easily in stackdriver and bigquery.
  json_handler = logging.StreamHandler()
  json_handler.setFormatter(kf_logging.CustomisedJSONFormatter())

  logger = logging.getLogger()
  logger.addHandler(json_handler)
  logger.setLevel(logging.INFO)

  fire.Fire(CLI)
