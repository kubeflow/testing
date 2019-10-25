"""Create a Kubeflow instance.

The purpose of this script is to automate the creation of Kubeflow Deployments
corresponding to different versions of Kubeflow.

This script should replace create_kf_instance. Unlike create_kf_instance
we no longer need to recycle kf app names because of IAP so we can
use unique names which greatly simplifies things.
This greatly simplifieds things. In particular, we don't need to do any
cleanup in this script because we will rely on cleanup_ci to GC old auto
deployments.
"""
import argparse
import datetime
import logging
import os
import re
import requests
import uuid
import yaml

from google.cloud import storage
from kubeflow.testing import util
from kubernetes import client as k8s_client
from retrying import retry

@retry(wait_fixed=60000, stop_max_attempt_number=5)
def run_with_retry(*args, **kwargs):
  util.run(*args, **kwargs)

def build_kfctl_go(args):
  """Build kfctl go."""
  build_dir = os.path.join(args.kubeflow_repo, "bootstrap")
  # We need to use retry builds because when building in the test cluster
  # we see intermittent failures pulling dependencies
  util.run(["make", "build-kfctl"], cwd=build_dir)
  kfctl_path = os.path.join(build_dir, "bin", "kfctl")

  return kfctl_path

def deploy_with_kfctl_go(kfctl_path, args, app_dir, env, labels=None):
  """Deploy Kubeflow using kfctl go binary."""
  # username and password are passed as env vars and won't appear in the logs
  #
  # We need to edit and rewrite the config file to the app dir because
  # kfctl uses the path of the config file as the app dir.s
  logging.warning("Loading configs %s.", args.kfctl_config)

  if args.kfctl_config.startswith("http"):
    response = requests.get(args.kfctl_config)
    raw_config = response.content
  else:
    with open(args.kfctl_config) as hf:
      raw_config = hf.read()

  config_spec = yaml.load(raw_config)

  # We need to specify a valid email because
  #  1. We need to create appropriate RBAC rules to allow the current user
  #     to create the required K8s resources.
  #  2. Setting the IAM policy will fail if the email is invalid.
  email = util.run(["gcloud", "config", "get-value", "account"])

  if not email:
    raise ValueError("Could not determine GCP account being used.")

  gcp_plugin = None
  for p in config_spec["spec"]["plugins"]:
    if p["kind"] != "KfGcpPlugin":
      continue
    gcp_plugin = p

  if not gcp_plugin:
    raise ValueError("No gcpplugin found in spec")
  gcp_plugin["spec"]["project"] = args.project
  gcp_plugin["spec"]["email"] = email
  gcp_plugin["spec"]["zone"] = args.zone

  config_spec["spec"] = util.filter_spartakus(config_spec["spec"])

  # Remove name because we will auto infer from directory.
  if "name" in config_spec["metadata"]:
    logging.info("Deleting name in kfdef spec.")
    del config_spec["metadata"]["name"]

  app_name = os.path.basename(app_dir)
  if not "labels" in config_spec["metadata"]:
    config_spec["metadata"]["labels"] = {}

  if labels:
    config_spec["metadata"]["labels"].update(labels)

  logging.info("KFDefSpec:\n%s", yaml.safe_dump(config_spec))

  if not os.path.exists(app_dir):
    logging.info("Creating app dir %s", app_dir)
    os.makedirs(app_dir)

  config_file = os.path.join(app_dir, "kf_config.yaml")
  with open(config_file, "w") as hf:
    logging.info("Writing file %s", config_file)
    yaml.dump(config_spec, hf)

  util.run([kfctl_path, "apply", "-V", "-f", config_file], env=env)

  # We will hit lets encrypt rate limiting with the managed certificates
  # So create a self signed certificate and update the ingress to use it.
  util.load_kube_config(persist_config=False)
  api_client = k8s_client.ApiClient()
  ingress_namespace = "istio-system"
  ingress_name = "envoy-ingress"
  tls_endpoint = "{0}.endpoints.{1}.cloud.goog".format(app_name, args.project)
  logging.info("Configuring self signed cert for %s", tls_endpoint)
  util.use_self_signed_for_ingress(ingress_namespace, ingress_name,
                                   tls_endpoint, api_client)

def main(): # pylint: disable=too-many-locals,too-many-statements
  logging.basicConfig(level=logging.INFO,
                            format=('%(levelname)s|%(asctime)s'
                                '|%(pathname)s|%(lineno)d| %(message)s'),
                        datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)

  parser = argparse.ArgumentParser()

  parser.add_argument(
          "--project", default="kubeflow-ci-deployment", type=str,
            help=("The project."))

  parser.add_argument(
          "--zone", default="us-east1-d", type=str, help=("The zone to deploy in."))
  parser.add_argument(
          "--oauth_file",
            default=("gs://kubeflow-ci-deployment_kf-data/"
                     "kf-iap-oauth.kubeflow-ci-deployment.yaml"),
      type=str, help=("The file containing the OAuth client ID & secret"
                    "for IAP."))

  parser.add_argument(
          "--kubeflow_repo",
            default="/src/kubeflow/kubeflow",
      type=str, help=("Path to the Kubeflow repo to use"))

  parser.add_argument(
          "--kfctl_config",
            default=("https://raw.githubusercontent.com/kubeflow/manifests"
                     "/master/kfdef/kfctl_gcp_iap.yaml"),
            type=str, help=("Path to the kfctl config to use"))

  parser.add_argument(
          "--apps_dir",
            default=os.getcwd(),
      type=str, help=("Directory to store kubeflow apps."))

  parser.add_argument(
          "--name", type=str, default="kf-vmaster-{uid}",
          help=("Name for the deployment. This can be a python format string "
                "with the variable uid. Uid will automatically be substituted "
                "for a unique value based on the time."))

  parser.add_argument(
          "--job_name",
            default="", type=str, help=("Pod name running the job."))

  args = parser.parse_args()

  util.maybe_activate_service_account()

  bucket, blob_path = util.split_gcs_uri(args.oauth_file)

  client = storage.Client(project=args.project)
  bucket = client.get_bucket(bucket)

  blob = bucket.get_blob(blob_path)
  contents = blob.download_as_string()

  oauth_info = yaml.load(contents)

  git_describe = util.run(["git", "describe", "--tags", "--always", "--dirty"],
                           cwd=args.kubeflow_repo).strip("'")

  kfctl_path = build_kfctl_go(args)

  # We need to keep the name short to avoid hitting limits with certificates.
  uid = datetime.datetime.now().strftime("%m%d") + "-"
  uid = uid + uuid.uuid4().hex[0:3]

  args.name = args.name.format(uid=uid)
  logging.info("Using name %s", args.name)

  app_dir = os.path.join(args.apps_dir, args.name)

  if not os.path.exists(args.apps_dir):
    os.makedirs(args.apps_dir)

  env = {}
  env.update(os.environ)
  env.update(oauth_info)

  # GCP labels can only take as input alphanumeric characters, hyphens, and
  # underscores. Replace not valid characters with hyphens.
  labels = {"git": git_describe,
            "purpose": "kf-test-cluster",}

  for k, v in labels.items():
    val = v.lower().replace("\"", "")
    val = re.sub(r"[^a-z0-9\-_]", "-", val)
    labels[k] = v

  deploy_with_kfctl_go(kfctl_path, args, app_dir, env, labels=labels)

if __name__ == "__main__":
  main()
