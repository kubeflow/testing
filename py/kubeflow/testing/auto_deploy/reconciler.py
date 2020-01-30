"""The reconciler for autodeployments.

The reconciler is responsible for launching K8s jobs to deploy
Kubeflow as needed and garbage collecting old instances
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
from kubeflow.testing import gcp_util
from kubeflow.testing import git_repo_manager
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

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
    if c.type.lower() in ["succeeded", "failed"]:
      if c.status.lower() in ["true"]:
        return False

  return True

class Reconciler:
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

  @staticmethod
  def from_config_file(config_path, job_template_path, local_dir=None):
    """Construct a reconciler from the config path.

    Args:
      config_path: Path to configuration
      job_template_path: Path to the YAML file containing a K8s job to
        launch to do the deployments.
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

    service_account_path = "/var/run/secrets/kubernetes.io"
    if os.path.exists("/var/run/secrets/kubernetes.io"):
      logging.info(f"{service_account_path} exists; loading in cluster config")
      k8s_config.load_incluster_config()
    else:
      logging.info(f"{service_account_path} doesn't exists; "
                    "loading kube config file")
      k8s_config.load_kube_config(persist_config=False)

    reconciler._k8s_client = k8s_client.ApiClient()
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
        logging.info("Skipping deployment %s; its missing the label", d["name"])

      name = auto_deploy_util.AutoDeploymentName.from_deployment_name(d["name"])

      if not name:
        logging.info("Skipping deployment %s; it is not an auto-deployed instance",
                     d["name"])
        continue

      if auto_deploy_util.is_storage_deployment(d["name"]):
        logging.info(f"Skipping deployment {d['name']}; it is storage")
        continue

      logging.info("Deployment %s is auto deployed", d["name"])

      # TODO(jlewi): We should add a label to the deployment to get the branch
      # rather than relying on the name
      manifests_branch = name.version

      create_time = date_parser.parse(d.get("insertTime"))
      deployment = auto_deploy_util.AutoDeployment(manifests_branch=manifests_branch,
                                                   create_time=create_time,
                                                   deployment_name=d["name"],
                                                   labels=labels)

      version_name = labels.get(auto_deploy_util.AUTO_NAME_LABEL, "unknown")
      logging.info(f"Found deployment={d['name']} for version={version_name}")
      self._deployments[version_name] = (self._deployments[version_name] +
                                         [deployment])

    # Sort the values by timestamp
    branches = self._deployments.keys()
    for b in branches:
      self._deployments[b] = sorted(self._deployments[b],
                                    key=lambda x: x.create_time)

  def _launch_job(self, config, commit):
    """Launch a K8s job to deploy Kubeflow.

    Args:
      config: The deployment config; contains the URL of the repo.
      commit: The commit to launch from.
    """
    # Check if there is already a running job
    label_filter = {
      auto_deploy_util.MANIFESTS_COMMIT_LABEL: commit,
    }

    items = [f"{k}={v}" for k, v in label_filter.items()]
    selector = ",".join(items)

    namespace = self.config["namespace"]
    # TODO(jlewi): We should switch to using Tekton.
    batch_api = k8s_client.BatchV1Api(self._k8s_client)
    jobs = batch_api.list_namespaced_job(namespace, label_selector=selector)

    if jobs.items:
      for j in jobs.items:
        self._log(logging.INFO, f"Found job {j.metadata.name}")

        if _job_is_running(j):
          self._log(logging.INFO, logging.info, f"Job {j.metadata.name} is still running; not launching "
                    f"a new job")

    with open(self._job_template_path) as f:
      job_config = yaml.load(f)

    job_config["metadata"]["generateName"] = f"auto-deploy-{config['name']}-"

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
      # We need to use a self signed certificate otherwise we hit lets
      # encrypt quota issues
      # TODO(jlewi): The code to use self cert was giving me problems.
      #"--use_self_cert",
    ]

    # TODO(jlewi): Handle errors
    try:
      job = batch_api.create_namespaced_job(namespace, job_config)
    except rest.ApiException as e:
      logging.error(f"Could not submit Kubrnetes job:\n{e}",
                    extra=self._log_context)

    self._log(logging.INFO, logging.info,
              f"Submitted job {job.metadata.namespace}.{job.metadata.name}")

  def _gc_deployments(self):
    """Delete old deployments"""

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
                       f"{next_oldest.deployment_nam} is only "
                       f"{next_age}(HH:MM:SS) old",
                       extra=self._log_context)
          break

        raise NotImplementedError("Need to call deleter")

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
      kf_def_url = _parse_kfdef_url(config[KFDEF_KEY])
      self._log_context = {
        "version_name": config["name"],
        "branch": kf_def_url.branch,
      }
      self._log(logging.INFO, f"Reconciling deployment {config['name']}")
      branch = kf_def_url.branch
      full_branch = f"{self._manifests_repo.remote_name}/{branch}"
      last_commit = self._manifests_repo.last_commit(full_branch, "")
      self._log(logging.INFO, logging.info, f"Last commit to branch={branch} {last_commit}")

      # Get the commit of the last deployment for this version
      if self._deployments[branch]:
        last_deployed = self._deployments[branch][-1]
        last_deployed_commit = last_deployed.labels.get(
          auto_deploy_util.MANIFESTS_COMMIT_LABEL)

        self._log(logging.INFO, f"Branch={branch} last_commit={last_commit} most recent "
                  f"deployment is at commit={last_deployed_commit}",
                     )

        if last_deployed_commit == last_commit:
          self._log(logging.INFO, f"Branch={branch} no sync needed")
          continue

        now = datetime.datetime.now(tz=last_deployed.create_time.tzinfo)
        time_since_last_deploy = now - last_deployed.create_time

        if time_since_last_deploy < MIN_TIME_BETWEEN_DEPLOYMENTS:
          minutes = time_since_last_deploy.total_seconds() / 60.0
          logging.info(f"Branch={branch} can't start a new deployment "
                       f"because deployment for {last_deployed.deployment_name }"
                       f"is only {minutes} minutes old", extra=self._log_context)
          continue
      else:
        logging.info(f"Branch={branch} has no active deployments",
                     extra=self._log_context)

      if active_deployments >= MAX_ACTIVE_DEPLOYMENTS:
        logging.info(f"Branch={branch} can't start a new deployment "
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

    while True:
      self._reconcile()
      logging.info(f"Wait {period}(HH:MM:SS) before reconciling; ")
      time.sleep(period.total_seconds())

class CLI:
  @staticmethod
  def run(config_path, job_template_path, local_dir=None):
    reconciler = Reconciler.from_config_file(config_path, job_template_path,
                                             local_dir=local_dir)
    reconciler.run()

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(CLI)
