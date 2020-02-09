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
import json
import logging
import os
import re
import requests
import retrying
import tempfile
import uuid
import yaml

from googleapiclient import discovery
from googleapiclient import errors
from google.cloud import storage
from kubeflow.testing import util
from kubernetes import client as k8s_client
from kubernetes.client import rest
from oauth2client.client import GoogleCredentials

KFDEF_V1ALPHA1 = "kfdef.apps.kubeflow.org/v1alpha1"

def build_kfctl_go(args):
  """Build kfctl go."""
  # We need to use retry builds because when building in the test cluster
  # we see intermittent failures pulling dependencies
  util.run(["make", "build-kfctl"], cwd=args.kubeflow_repo)
  kfctl_path = os.path.join(args.kubeflow_repo, "bin", "kfctl")

  return kfctl_path

def build_v06_spec(config_spec, project, email, zone, setup_project):
  """Create a v0.6 KFDef spec."""

  config_spec["spec"]["project"] = project
  config_spec["spec"]["email"] = email
  config_spec["spec"]["zone"] = zone
  config_spec["spec"]["skipInitProject"] = not setup_project
  return config_spec

def build_v07_spec(config_spec, project, email, zone, setup_project):
  """Create a v0.7 or later KFDef spec."""
  gcp_plugin = None
  for p in config_spec["spec"]["plugins"]:
    if p["kind"] != "KfGcpPlugin":
      continue
    gcp_plugin = p

  if not gcp_plugin:
    raise ValueError("No gcpplugin found in spec")
  gcp_plugin["spec"]["project"] = project
  gcp_plugin["spec"]["email"] = email
  gcp_plugin["spec"]["zone"] = zone
  gcp_plugin["spec"]["skipInitProject"] = not setup_project

  return config_spec

class ApiNotEnabledError(Exception):
  pass

def retry_if_api_not_enabled_error(exception):
  """Return True if we should retry.

     In this case when it's ApiNotEnabled error), False otherwise"""
  return isinstance(exception, ApiNotEnabledError)

# We may need to retry if the deployment manager API isn't enabled.
# However we also observe problems with gcloud timing out trying to enable
# the API so we may need to retry enabling the API multiple times.
# TODO(jlewi): We can probably decrease retries; errors for gcloud timing
# out are related to workload identity and retrying for long periods doesn't
# seem to help
@retrying.retry(stop_max_delay=1*60*1000)
def check_if_kfapp_exists(project, name, zone): # pylint: disable=too-many-branches
  """Check if a deployment with the specified name already exists."""
  credentials = GoogleCredentials.get_application_default()
  dm = discovery.build("deploymentmanager", "v2", credentials=credentials)

  deployments_client = dm.deployments()
  enable_api = False
  try:
    deployments_client.get(project=project, deployment=name).execute()
  except errors.HttpError as e:
    if not e.content:
      raise
    error_content = json.loads(e.content)
    if error_content.get("error", {}).get("code", 0) == 404: # pylint: disable=no-else-return
      return False
    elif error_content.get("error", {}).get("code", 0) == 403:
      # We get a 403 if the deployment manager API isn't enabled
      logging.info("Fetching deployment %s in project %s returned error:\n%s",
                   name, project, error_content)
      enable_api = True
    else:
      raise

  if enable_api:
    logging.info("Enabling the deployment manager api.")
    util.run(["gcloud", "--project=" + project, "services", "enable",
              "deploymentmanager.googleapis.com"])
    logging.info("Api enabled; raising ApiNotEnabledError to force retry")
    raise ApiNotEnabledError

  # TODO(jlewi): It would be better to get the actual zone of the deployment
  util.run(["gcloud", "--project=" + project, "container", "clusters",
            "get-credentials", "--zone=" + zone, name])
  logging.info("Checking if project %s kfapp %s finished setup.", project, name)
  util.load_kube_credentials()

  # TODO(jlewi): This is a bit of a hack for v0.6. For v0.6 we check if the
  # ingress already exists and if it does we report it as true and otherwise
  # false. The reasoning is if the ingress doesn't exist we want to see
  # if we can fix/resume the deployment by running reapply
  # With v0.7 kfctl apply should be an idempotent operation so we can always
  # rerun apply; but with v0.6 rerunning apply if the ingress exists results
  # in an error.
  api_client = k8s_client.ApiClient()
  v1 = k8s_client.CoreV1Api(api_client)
  ingress_namespace = "istio-system"
  ingress_name = "envoy-ingress"

  extensions = k8s_client.ExtensionsV1beta1Api(api_client)

  missing_ingress = True
  try:
    logging.info("Trying to read ingress %s.%s", ingress_name,
                 ingress_namespace)
    extensions.read_namespaced_ingress(ingress_name, ingress_namespace)
    missing_ingress = False
    logging.info("Ingress %s.%s exists", ingress_name, ingress_namespace)
  except rest.ApiException as e:
    if e.status == 404:
      logging.info("Project: %s, KFApp: %s is missing ingress %s.%s",
                   project, name, ingress_namespace, ingress_name)
      missing_ingress = True
    else:
      raise

  if missing_ingress:
    # Check if the service istio-ingressgateway already exists
    # if it does we need to delete it before rerunning apply.
    service_name = "istio-ingressgateway"
    logging.info("ingress %s.%s exists; checking if service %s.%s exists",
                 ingress_namespace, ingress_name, ingress_namespace,
                 service_name)

    has_service = False
    try:
      v1.read_namespaced_service(service_name, ingress_namespace)
      has_service = True
    except rest.ApiException as e:
      if e.status == 404:
        logging.info("Project: %s, KFApp: %s is missing service %s.%s",
                     project, name, ingress_namespace, service_name)
      else:
        raise

    if has_service:
      logging.info("Deleting service: %s.%s", ingress_namespace, service_name)
      v1.delete_namespaced_service(service_name, ingress_namespace,
                                   body=k8s_client.V1DeleteOptions())
      logging.info("Deleted service: %s.%s", ingress_namespace, service_name)

    return False


  return True

def deploy_with_kfctl_go(kfctl_path, args, app_dir, env, labels=None): # pylint: disable=too-many-branches
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
  email = args.email

  if not email:
    logging.info("email not set trying to get default from gcloud")
    email = util.run(["gcloud", "auth", "list",
                      "--filter", "status:ACTIVE", "--format", "value(account)"])

  if not email:
    raise ValueError("Could not determine GCP account being used.")

  kfdef_version = config_spec["apiVersion"].strip().lower()

  if kfdef_version == KFDEF_V1ALPHA1:
    config_spec = build_v06_spec(config_spec, args.project, email, args.zone,
                                 args.setup_project)
  else:
    config_spec = build_v07_spec(config_spec, args.project, email, args.zone,
                                 args.setup_project)

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

  if kfdef_version == KFDEF_V1ALPHA1:
    logging.info("Deploying using v06 syntax")

    logging.info("Checking if deployment %s already exists in project %s",
                 args.project, app_name)

    if check_if_kfapp_exists(args.project, app_name, args.zone):
      # With v0.6 kfctl can't successfully run apply a 2nd time so if
      # the deployment already exists we can't redeploy.
      logging.info("Deployment %s already exists in project %s; not "
                   "redeploying", args.project, app_name)
      return

    with tempfile.NamedTemporaryFile(prefix="tmpkf_config", suffix=".yaml",
                                     delete=False) as hf:
      config_file = hf.name
      logging.info("Writing file %s", config_file)
      yaml.dump(config_spec, hf)

    util.run([kfctl_path, "init", app_dir, "-V", "--config=" + config_file],
             env=env)

    util.run([kfctl_path, "generate", "-V", "all"], env=env, cwd=app_dir)

    util.run([kfctl_path, "apply", "-V", "all"], env=env, cwd=app_dir)
  else:
    logging.info("Deploying using v07 syntax")

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
  if args.use_self_cert:
    logging.info("Configuring self signed certificate")

    util.load_kube_credentials()

    api_client = k8s_client.ApiClient()
    ingress_namespace = "istio-system"
    ingress_name = "envoy-ingress"
    tls_endpoint = "{0}.endpoints.{1}.cloud.goog".format(app_name, args.project)
    logging.info("Configuring self signed cert for %s", tls_endpoint)
    util.use_self_signed_for_ingress(ingress_namespace, ingress_name,
                                     tls_endpoint, api_client)

# gcloud appears to timeout so lets add some retries.
@retrying.retry(stop_max_delay=4*60*1000)
def add_extra_users(project, extra_users):
  """Grant appropriate permissions to additional users."""
  logging.info("Adding additional IAM roles")
  extra_users = extra_users.strip()
  users = extra_users.split(",")
  for user in users:
    if not user:
      continue
    logging.info("Granting iap.httpsResourceAccessor to %s", user)
    util.run(["gcloud", "projects",
               "add-iam-policy-binding", project,
               "--member=" + user,
               "--role=roles/iap.httpsResourceAccessor"])

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

  # TODO(jlewi): Should rename this argument to something like kfctl_src
  # We should try to do it in a backwards compatible way.
  parser.add_argument(
          "--kubeflow_repo",
            default="/src/kubeflow/kubeflow",
      type=str, help=("Path to the source for kfctl. Should be the directory "
                      "containing the Makefile to build kfctl"))

  parser.add_argument(
          "--kfctl_path",
            default="",
      type=str, help=("Path to kfctl; can be a URL."))

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
          "--email", type=str, default="",
          help=("(Optional). Email of the person to create the default profile"
                "for. If not specificied uses the gcloud config value."))

  parser.add_argument(
          "--extra_users", type=str, default="",
          help=("Comma separated list of additional users to grant access. "
                "Should be in the form user:donald@google.com or"
                "serviceAccount:test123@example.domain.com"))

  parser.add_argument("--setup_project", dest="setup_project",
                      action="store_true", help="Setup the project")
  parser.add_argument("--no-setup_project", dest="setup_project",
                      action="store_false", help="Do not setup the project")
  parser.set_defaults(setup_project=True)

  parser.add_argument("--use_self_cert", dest="use_self_cert",
                      action="store_true",
                      help="Use a self signed certificate")
  parser.add_argument("--no-use_self_cert", dest="use_self_cert",
                      action="store_false",
                      help="Do not use a self signed certificate")
  parser.set_defaults(use_self_cert=True)

  args = parser.parse_args()

  util.maybe_activate_service_account()

  # For debugging purposes output the command
  util.run(["gcloud", "config", "list"])
  util.run(["gcloud", "auth", "list"])

  bucket, blob_path = util.split_gcs_uri(args.oauth_file)

  client = storage.Client(project=args.project)
  bucket = client.get_bucket(bucket)

  blob = bucket.get_blob(blob_path)
  contents = blob.download_as_string()

  oauth_info = yaml.load(contents)

  if args.kubeflow_repo and args.kfctl_path:
    raise ValueError("Exactly one of --kubeflow_repo and --kfctl_path neeeds "
                     "to be set.")

  if not args.kubeflow_repo and not args.kfctl_path:
    raise ValueError("Exactly one of --kubeflow_repo and --kfctl_path neeeds "
                     "to be set.")

  git_describe = ""
  if args.kubeflow_repo:
    git_describe = util.run(["git", "describe", "--tags", "--always", "--dirty"],
                             cwd=args.kubeflow_repo).strip("'")

    kfctl_path = build_kfctl_go(args)
  else:
    if args.kfctl_path.startswith("http"):
      temp_dir = tempfile.mkdtemp()
      util.run(["curl", "-L", "-o", "kfctl.tar.gz", args.kfctl_path],
               cwd=temp_dir)
      util.run(["tar", "-xvf", "kfctl.tar.gz"], cwd=temp_dir)
      kfctl_path = os.path.join(temp_dir, "kfctl")
      git_describe = util.run([kfctl_path, "version"])
    else:
      kfctl_path = args.kfctl_path

  logging.info("kfctl path set to %s", kfctl_path)

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
            "purpose": "kf-test-cluster",
            "auto-deploy": "true"}

  for k, v in labels.items():
    val = v.lower().replace("\"", "")
    val = re.sub(r"[^a-z0-9\-_]", "-", val)
    labels[k] = val

  deploy_with_kfctl_go(kfctl_path, args, app_dir, env, labels=labels)
  add_extra_users(args.project, args.extra_users)

if __name__ == "__main__":
  main()
