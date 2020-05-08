"""Create a Kubeflow instance using a GCP blueprint.

The purpose of this script is to automate the creation of Kubeflow Deployments
corresponding to different versions of Kubeflow.

This script should replace create_kf_instance and potentially
create_unique_kf_instance.py.

Unlike create_unique_kf_instance.py this script

1. Uses GCP blueprints(https://github.com/kubeflow/gcp-blueprints) to deploy
   kubeflow
2. This script doesn't do any Git checkouts.
   * Assumption is Git repos are already checkout (e.g. via Tekton)

This script doesn't do any cleanup wecause we will rely on cleanup_ci to GC old
auto deployments.

TODO(jlewi): We should add commonLabels to all the GCP infrastructure to
make it easy to delete.
"""
import datetime
import fire
import logging
import os
import re
import retrying
import subprocess
import uuid
import yaml

from google.cloud import storage
from kubeflow.testing import gcp_util
from kubeflow.testing import util


DEFAULT_OAUTH_FILE = ("gs://kubeflow-ci-deployment_kf-data/"
                      "kf-iap-oauth.kubeflow-ci-deployment.yaml")

class ApiNotEnabledError(Exception):
  pass

def get_oauth(project, oauth_file):
  """Get the OAuth information"""
  bucket, blob_path = util.split_gcs_uri(oauth_file)

  client = storage.Client(project=project)
  bucket = client.get_bucket(bucket)

  blob = bucket.get_blob(blob_path)
  contents = blob.download_as_string()

  oauth_info = yaml.load(contents)
  return oauth_info

def add_common_labels(kustomization_file, labels):
  kustomize_dir = os.path.dirname(kustomization_file)
  for k, v in labels.items():
    # We shell out to kustomize edit because we want to preserve
    # comments and kpt annotations in the file.
    util.run(["kustomize", "edit", "add", "label", "-f", f"{k}:{v}"],
             cwd=kustomize_dir)


class BlueprintRunner:
  @staticmethod
  def deploy(blueprint_dir, management_context, name="kf-vbp-{uid}",
             project="kubeflow-ci-deployment",
             location="us-central1", zone="us-central1-f",
             labels_file=None,
             oauth_file=DEFAULT_OAUTH_FILE): # pylinet: disable=too-many-arguments
    """Deploy the blueprint:

    Args:
      blueprint_dir: The directory where
         https://github.com/kubeflow/gcp-blueprints/tree/master/kubeflow is checked
         out.
      management_context: The name of the management context.
      name: Name for the deployment. This can be a python format string
            with the variable uid. Uid will automatically be substituted "
          for a unique value based on the time.
      project: The GCP project where the blueprint should be created.
      location: The zone or region where Kubeflow should be deployed.
      zone: The zone to use for disks must be in the same region as location
        when using a regional cluster and must be location when location
        is zone.
      labels_file: (Optional): Path to a file containing additional labels
        to add to the deployment.
      oauth_file: The file containing the OAuth client ID & secret for IAP.
    """
    # Wait for credentials to deal with workload identity issues
    gcp_util.get_gcp_credentials()

    try:
      util.run(["make", "get-pkg"], cwd=blueprint_dir)
    except subprocess.CalledProcessError as e:
      if re.search(".*resources must be annotated with config.kubernetes.io/"
                   "index.*", e.output):
        logging.warning(f"make get-pkg returned error: {e.output}; ignoring "
                        "and continuing")

      elif re.search(".*already exists.*", e.output):
        logging.warning("The package directory already exists; continuing")
      else:
        logging.error(f"Command exited with error: {e.output}")
        raise

    util.run(["kpt", "cfg", "set", "instance", "mgmt-ctxt", management_context],
             cwd=blueprint_dir)

    # We need to keep the name short to avoid hitting limits with certificates.
    uid = datetime.datetime.now().strftime("%m%d") + "-"
    uid = uid + uuid.uuid4().hex[0:3]

    name = name.format(uid=uid)
    logging.info("Using name %s", name)

    values = {
      "name": name,
      "gcloud.core.project": project,
      "gcloud.compute.zone": zone,
      "location": location,
    }

    for subdir in ["./upstream/manifests/gcp", "./instance"]:
      for k, v in values.items():
        util.run(["kpt", "cfg", "set", subdir, k, v],
                 cwd=blueprint_dir)

    # TODO(jlewi): We should add an expiration time; either as a label
    # or as as an annotation.
    # GCP labels can only take as input alphanumeric characters, hyphens, and
    # underscores. Replace not valid characters with hyphens.
    # TODO(jlewi): We are assuming all blueprints created by
    # create_kf_from_gcp_blueprint.py are auto-deployed. How could
    # we inject appropriate labels when creating auto-deploy jobs?
    labels = {}

    if labels_file:
      logging.info(f"Reading labels from file: {labels_file}")

      pattern = re.compile("([^=]+)=(.+)")
      with open(labels_file) as f:
        while True:
          l = f.readline()
          if not l:
            break
          m = pattern.match(l)
          if not m:
            logging.info(f"Skipping line {l} it doesn't match pattern "
                         f"{pattern.pattern}")
          labels[m.group(1)] = m.group(2)
    else:
      logging.info("No labels file provided.")


    kustomization_file = os.path.join(blueprint_dir, "instance", "gcp_config",
                                      "kustomization.yaml")

    add_common_labels(kustomization_file, labels)

    oauth_info = get_oauth(project, oauth_file)

    env = {}
    env.update(os.environ)
    env.update(oauth_info)

    # To work around various bugs in our manifests that can be fixed by
    # retrying we see if a particular error occurs and then retry.
    # As thes issues are fixed we should remove the retries.
    retryable_errors = [
      # TODO(https://github.com/kubeflow/manifests/issues/1149):
      # Once this is fixed we should be able to remove this.
      re.compile(".*no matches for kind \"Application\" in version "
                 "\"app.k8s.io/v1beta1\""),
    ]

    # The total time to wait needs to take into account the actual time
    # it takes to run otherwise we won't retry.
    total_time = datetime.timedelta(minutes=30)

    def is_retryable_esception(exception):
      """Return True if we should retry False otherwise"""

      if not isinstance(exception, subprocess.CalledProcessError):
        return False

      for m in retryable_errors:
        if m.search(exception.output):
          logging.warning("make apply failed with retryable error. The "
                          f"output matched regex: {m.pattern}")
          return True

      return False

    @retrying.retry(stop_max_delay=total_time.total_seconds() * 1000,
                    retry_on_exception=is_retryable_esception)
    def run_apply():
      util.run(["make", "apply"], cwd=blueprint_dir, env=env)

    run_apply()

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  try:
    fire.Fire(BlueprintRunner)
  except subprocess.CalledProcessError as e:
    logging.error(f"Subprocess exited with error; output:\n{e.output}")
    raise
