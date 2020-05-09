"""The reconciler for autodeployments.

The reconciler is responsible for launching K8s jobs to deploy
Kubeflow as needed and garbage collecting old instances

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

from kubeflow.testing.auto_deploy import util as auto_deploy_util
from kubeflow.testing import delete_kf_instance
from kubeflow.testing import gcp_util
from kubeflow.testing import git_repo_manager
from kubeflow.testing import kf_logging
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client import rest
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

# The minimum time to wait before triggering another deployment.
MIN_TIME_BETWEEN_DEPLOYMENTS = datetime.timedelta(minutes=20)

# The maximum number of active deployments
# TODO(jlewi): Maybe bump this later on.
MAX_ACTIVE_DEPLOYMENTS = 10

KFDEF_URL_TUPLE = collections.namedtuple("KfDefUrlTuple",
                                         ("host", "owner", "repo", "branch",
                                          "path"))

KFDEF_PATTERN = re.compile("https://([^/]*)/([^/]*)/([^/]*)/([^/]*)/(.*)")

# Name of various keys in the config file
KFDEF_KEY = "kfDefUrl"
KFCTL_KEY = "kfctlUrl"
VERSIONS_KEY = "versions"

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

def _parse_kfdef_url(url):
  m = KFDEF_PATTERN.match(url)
  if not m:
    raise ValueError(f"url {url} doesn't match pattern {m.pattern}")
  return KFDEF_URL_TUPLE(m.group(1), m.group(2), m.group(3), m.group(4),
                         m.group(5))

def _kfdef_url_to_clone_url(url):
  """Convert the KFDef URL into the repo to clone"""
  # TODO(jlewi): For other hosts how would we determine the repo to clone?
  # Maybe make it explicitly set in the config file
  if url.host != "raw.githubusercontent.com":
    raise ValueError("The code currently assumes KFDef are hosted on "
                     "raw.githubusercontent.com")
  return f"https://github.com/{url.owner}/{url.repo}.git"

def _job_is_running(j):
  """Return true if the specified K8s job is still running.

  Args:
    j: A K8s job object
  """
  conditions = j.status.conditions

  if not conditions:
    return True

  for c in conditions[::-1]:
    if c.type.lower() in ["succeeded", "failed", "complete"]:
      if c.status.lower() in ["true"]:
        return False

  return True

class Reconciler: # pylint: disable=too-many-instance-attributes
  def __init__(self, manifests_repo=None, config=None, job_template_path=None):
    """Construct a reconciler

    Args:
      manifests_repo: A GitRepoManager object representing the
        kubeflow/manifests repo
      config: A dictionary containing the
      job_template_path: Path to the YAML file for the K8s job to
       launch.
    """
    self.config = config
    # This is a map:
    # Kubeflow version -> List of deployments
    self._deployments = None

    self._manifests_repo = manifests_repo

    self._k8s_client = None
    self._job_template_path = job_template_path

    # Logging context. A dictionary of extra labels for logs
    self._log_context = {}

    # If provided this should be a multiprocessing queue on which to
    # push info about deployments
    self._queue = None

    # Directory where YAML files listing deployments should be written.
    # This is used to make it available to other processes
    self._deployments_dir = None

    self._manifests_client = None

  @staticmethod
  def from_config_file(config_path, job_template_path, deployments_dir,
                       local_dir=None):
    """Construct a reconciler from the config path.

    Args:
      config_path: Path to configuration
      job_template_path: Path to the YAML file containing a K8s job to
        launch to do the deployments.
      deployments_dir: Path where YAML should be dumped describing deployments
      local_dir: (Optional): Path were repositories should be checked out.
    """
    with open(config_path) as f:
      config = yaml.load(f)

    kfdef_url = _parse_kfdef_url(config[VERSIONS_KEY][0][KFDEF_KEY])

    # Ensure there is a single repository; currently the code only handles
    # the case where all deployments are from a single URL
    for d in config[VERSIONS_KEY][1:]:
      new_url = _parse_kfdef_url(d[KFDEF_KEY])

      if (new_url.host != kfdef_url.host or new_url.owner != kfdef_url.owner
          or new_url.repo != kfdef_url.repo):
        raise ValueError(f"All deployments must use the same repo for the KFDef")

    url = _kfdef_url_to_clone_url(kfdef_url)

    manifests_repo = git_repo_manager.GitRepoManager(url=url,
                                                     local_dir=local_dir)
    reconciler = Reconciler(config=config, job_template_path=job_template_path,
                            manifests_repo=manifests_repo)


    reconciler._deployments_dir = deployments_dir # pylint: disable=protected-access
    logging.info(f"Using deployments directory={reconciler._deployments_dir}") # pylint: disable=protected-access

    service_account_path = "/var/run/secrets/kubernetes.io"
    if os.path.exists("/var/run/secrets/kubernetes.io"):
      logging.info(f"{service_account_path} exists; loading in cluster config")
      k8s_config.load_incluster_config()
    else:
      logging.info(f"{service_account_path} doesn't exists; "
                    "loading kube config file")
      k8s_config.load_kube_config(persist_config=False)

    reconciler._k8s_client = k8s_client.ApiClient() # pylint: disable=protected-access
    return reconciler

  # TODO(jlewi): This was a failed attempt to create a utility function
  # to always log the context. It turns out to lead to inconvenient code
  # because we need to set the level. I think we want to define
  # self.logging which has functions info, debug, warning, error etc...
  def _log(self, level, message, *args, **kwargs):
    if "extra" not in kwargs:
      kwargs["extra"] = {}

    kwargs["extra"].update(self._log_context)
    logging.log(level, message, *args, **kwargs)

  def _save_deployments(self):
    if not self._deployments_dir:
      logging.info("No deployments directory provided; not persisting "
                   "deployments")
      return
    # Write to the deployments to a file in order to make them
    # available to all the flask threads and processes
    suffix = datetime.datetime.now().strftime("%y%m%d-%H%M%S")

    if not os.path.exists(self._deployments_dir):
      os.makedirs(self._deployments_dir)

    d = {}
    for k, v in self._deployments.items():
      d[k] = [i.to_dict() for i in v]

    path = os.path.join(self._deployments_dir, f"deployments.{suffix}.yaml")

    logging.info(f"Writing deployments to {path}")
    with open(path, "w") as hf:
      yaml.dump(d, hf)

    # TODO(jlewi): We should GC old versions of the file.

  def _get_deployment_zone(self, deployment_name, manifest_name):
    """Get the zone for a deployment.

    Args:
      deployment_name: Name of the deployment
      manifest_name: Name of the manifest

    Returns:
      zone:
    """
    if not self._manifests_client:
      credentials = GoogleCredentials.get_application_default()
      dm = discovery.build("deploymentmanager", "v2", credentials=credentials)

      self._manifests_client = manifests = dm.manifests()

    manifests = self._manifests_client

    m = manifests.get(project=self.config['project'],
                      deployment=deployment_name,
                      manifest=manifest_name).execute()

    dm_config = yaml.load(m["config"]["content"])
    zone = dm_config["resources"][0]["properties"]["zone"]

    return zone

  def _get_deployments(self, deployments=None):
    """Build a map of all deployments

    Args:
      deployments: (Optional) Iterator over GCP deployments.
    """
    logging.info("Building map of auto deployments")

    self._deployments = collections.defaultdict(lambda: [])
    if not deployments:
      deployments = gcp_util.deployments_iterator(self.config["project"])

    for d in deployments:
      is_auto_deploy = False
      # Use labels to identify auto-deployed instances
      labels = {}
      for label_pair in d.get("labels", []):
        # Newer clusters
        if label_pair["key"] == "auto-deploy":
          is_auto_deploy = True
        # Older clusters
        if (label_pair["key"] == "purpose" and
            label_pair["value"] == "kf-test-cluster"):
          is_auto_deploy = True
        labels[label_pair["key"]] = label_pair["value"]

      if not is_auto_deploy:
        logging.info("Skipping deployment %s; its missing the label "
                     "auto-deploy", d["name"])
        continue

      if d.get("operation", {}).get("operationType") == "delete":
        logging.info(f"Skipping deployment {d['name']} it is being deleted.")
      if auto_deploy_util.is_storage_deployment(d["name"]):
        logging.info(f"Skipping deployment {d['name']}; it is storage")
        continue

      version_name = labels.get(auto_deploy_util.AUTO_NAME_LABEL, "unknown")

      if not "manifest" in d:
        logging.error(f"Skipping deployment {d['name']} it doesn't "
                       "have a manifest")
        continue

      dm_manifest_name = d["manifest"].split("/")[-1]

      zone = self._get_deployment_zone(d["name"], dm_manifest_name)

      context = {
        "deployment_name" : d['name'],
        "version_name" : version_name,
      }

      manifests_branch = labels.get(auto_deploy_util.BRANCH_LABEL, "unknown")

      create_time = date_parser.parse(d.get("insertTime"))
      deployment = auto_deploy_util.AutoDeployment(manifests_branch=manifests_branch,
                                                   create_time=create_time,
                                                   deployment_name=d["name"],
                                                   labels=labels)
      deployment.zone = zone
      logging.info(f"Found auto deployment={d['name']} for version={version_name}",
                   extra=context)
      self._deployments[version_name] = (self._deployments[version_name] +
                                         [deployment])

    # Sort the values by timestamp
    branches = self._deployments.keys()
    for b in branches:
      self._deployments[b] = sorted(self._deployments[b],
                                    key=lambda x: x.create_time)

    self._save_deployments()

  def _launch_job(self, config, commit):
    """Launch a K8s job to deploy Kubeflow.

    Args:
      config: The deployment config; contains the URL of the repo.
      commit: The commit to launch from.
    """
    with open(self._job_template_path) as f:
      job_config = yaml.load(f)

    job_config["metadata"]["generateName"] = f"auto-deploy-{config['name']}-"

    if os.getenv("JOB_NAMESPACE"):
      namespace = os.getenv("JOB_NAMESPACE")
      logging.info(f"Setting job namespace to {namespace}",
                   extra=self._log_context)
      job_config["metadata"]["namespace"] = namespace

    namespace = job_config["metadata"]["namespace"]

    # Check if there is already a running job
    label_filter = {
      auto_deploy_util.MANIFESTS_COMMIT_LABEL: commit,
    }

    items = [f"{k}={v}" for k, v in label_filter.items()]
    selector = ",".join(items)

    # TODO(jlewi): We should switch to using Tekton.
    batch_api = k8s_client.BatchV1Api(self._k8s_client)
    jobs = batch_api.list_namespaced_job(namespace, label_selector=selector)

    if jobs.items:
      for j in jobs.items:
        logging.info(f"Found job {j.metadata.name}", extra=self._log_context)

        if _job_is_running(j):
          logging.info(
            f"Job {j.metadata.name} is still running; not launching "
            f"a new job",
            extra=self._log_context)
          return

    if os.getenv("JOB_NAMESPACE"):
      namespace = os.getenv("JOB_NAMESPACE")
      logging.info(f"Setting job namespace to {namespace}",
                   extra=self._log_context)
      job_config["metadata"]["namespace"] = namespace

    kfdef_url = _parse_kfdef_url(config[KFDEF_KEY])

    # Kubeflow deployment name
    # We need to keep the name short to avoid hitting limits with certificates.
    uid = datetime.datetime.now().strftime("%m%d") + "-"
    uid = uid + uuid.uuid4().hex[0:3]
    kf_name = f"kf-{config['name']}-{uid}"

    labels = {auto_deploy_util.MANIFESTS_COMMIT_LABEL: commit,
       auto_deploy_util.BRANCH_LABEL: kfdef_url.branch,
       auto_deploy_util.AUTO_NAME_LABEL: config["name"],
       "kf-name": kf_name,
    }

    # Make label value safe
    for k, _ in labels.items():
      labels[k] = labels[k].replace(".", "-")

    job_config["metadata"]["labels"].update(labels)

    label_pairs = [f"{k}={v}" for k, v in labels.items()]
    labels_value = ",".join(label_pairs)
    commit_url = (f"https://{kfdef_url.host}/{kfdef_url.owner}/"
                  f"{kfdef_url.repo}/{commit}/{kfdef_url.path}")

    job_config["spec"]["template"]["spec"]["containers"][0]["command"] = [
      "python",
      "-m",
      "kubeflow.testing.create_unique_kf_instance",
      "--apps_dir=/src/apps",
      # TODO(jlewi): Should we optionally support building kfctl?
      "--kfctl_path=" + config[KFCTL_KEY],
      "--kubeflow_repo=",
      f"--name=" + kf_name,
      f"--project={self.config['project']}",
      f"--zone={self.config['zone']}",
      "--kfctl_config=" + commit_url,
      # The job spec
      f"--labels={labels_value}",
       # Use self signed certificates otherwise we will have problem
       "--use_self_cert",
    ]

    namespace = job_config["metadata"]["namespace"]
    # TODO(jlewi): Handle errors
    try:
      job = batch_api.create_namespaced_job(namespace, job_config)
      full_name = f"{namespace}.{job.metadata.name}"
      logging.info(f"Submitted job {full_name}",
                   extra=self._log_context)

    except rest.ApiException as e:  # pylint: disable=unused-variable
      logging.error(f"Could not submit Kubernetes job for deployment {kf_name}"
                    ":\n{e}", extra=self._log_context)


  def _gc_deployments(self):
    """Delete old deployments"""
    kf_deleter = delete_kf_instance.KFDeleter()

    for name, deployments in self._deployments.items():
      self._log_context = {
        "version_name": name,
      }

      logging.info(f"Version {name} has {len(deployments)} active deployments",
                   extra=self._log_context)

      # We want at least one deployment for each version
      if len(deployments) <= 1:
        continue

      # deployments should already be sorted by create time.
      # we always want to keep at least 1 deployment so we never delete
      # the last deployment
      for index, d in enumerate(deployments[:-1]):
        now = datetime.datetime.now(d.create_time.tzinfo)
        age = now - d.create_time

        if age < MIN_LIFETIME:
          logging.info(f"Deployment {d.deployment_name} not eligible for deletion; "
                       f"It is only {age} old", extra=self._log_context)
          # Since all the other deployments will be younger none of them
          # will be eligible
          break

        # Make sure the next deployment is at least older than the GRACE_PERIOD
        # before deleting this one.
        next_oldest = deployments[index + 1]
        now = datetime.datetime.now(next_oldest.create_time.tzinfo)
        next_age = now - next_oldest.create_time

        if next_age < GRACE_PERIOD:
          logging.info(f"Deployment {d.deployment_name} not eligible for deletion; "
                       f"The next oldest deployment "
                       f"{next_oldest.deployment_name} is only "
                       f"{next_age}(HH:MM:SS) old",
                       extra=self._log_context)
          break

        context = {
          "deployment_name": d.deployment_name
        }
        context.update(self._log_context)
        logging.info(f"Deleting deployment {d.deployment_name}; age={age} "
                     f"create_time={d.create_time}", extra=context)
        kf_deleter.delete_kf(self.config["project"], d.deployment_name)

  def _reconcile(self):
    # Get the deployments.
    self._get_deployments()

    # Compute the current number of deployments
    active_deployments = 0
    for _, i in self._deployments.items():
      active_deployments += len(i)

    # Sync the repositories because we use this to find the latest changes.
    self._manifests_repo.fetch()

    # TODO(jlewi): Stop hardcoding the branch names we should pass this
    # in via some sort of config
    for config in self.config[VERSIONS_KEY]:
      version_name = config["name"]
      logging.info(f"Processing version={version_name}")
      kf_def_url = _parse_kfdef_url(config[KFDEF_KEY])
      self._log_context = {
        "version_name": config["name"],
        "branch": kf_def_url.branch,
      }
      self._log(logging.INFO, f"Reconciling deployment {config['name']}")
      branch = kf_def_url.branch
      full_branch = f"{self._manifests_repo.remote_name}/{branch}"
      last_commit = self._manifests_repo.last_commit(full_branch, "")
      logging.info(f"Last commit to version={version_name} "
                   "commit={last_commit}", extra=self._log_context)

      # Get the commit of the last deployment for this version
      if self._deployments[version_name]:
        last_deployed = self._deployments[version_name][-1]
        last_deployed_commit = last_deployed.labels.get(
          auto_deploy_util.MANIFESTS_COMMIT_LABEL)


        now = datetime.datetime.now(tz=last_deployed.create_time.tzinfo)
        time_since_last_deploy = now - last_deployed.create_time

        logging.info(f"version_name={version_name} "
                     f"last_commit={last_commit} most recent "
                     f"deployment is {last_deployed.deployment_name} "
                     f"at commit={last_deployed_commit} "
                     f"age={time_since_last_deploy}",
                     extra=self._log_context)

        if (last_deployed_commit == last_commit and
            time_since_last_deploy < PERIODIC_REDEPLOY):
          logging.info(f"version_name={version_name} no sync needed",
                       extra=self._log_context)
          continue
        else:
          logging.info(f"version_name={version_name} sync needed",
                       extra=self._log_context)

        if time_since_last_deploy < MIN_TIME_BETWEEN_DEPLOYMENTS:
          minutes = time_since_last_deploy.total_seconds() / 60.0
          logging.info(f"version_name={version_name} can't start a new deployment "
                       f"because deployment for {last_deployed.deployment_name }"
                       f"is only {minutes} minutes old", extra=self._log_context)
          continue
      else:
        logging.info(f"version_name={version_name} has no active deployments",
                     extra=self._log_context)

      if active_deployments >= MAX_ACTIVE_DEPLOYMENTS:
        logging.info(f"version_name={version_name} can't start a new deployment "
                     f"there are currently {active_deployments} active "
                     f"deployments already.", extra=self._log_context)
        continue

      self._launch_job(config, last_commit)

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
  def run(config_path, job_template_path, deployments_dir, local_dir=None):
    reconciler = Reconciler.from_config_file(config_path, job_template_path,
                                             deployments_dir=deployments_dir,
                                             local_dir=local_dir)
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
