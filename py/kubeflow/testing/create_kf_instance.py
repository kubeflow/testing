"""Create a Kubeflow instance.

The purpose of this script is to automate the creation of Kubeflow Deployments
corresponding to different versions of Kubeflow.
"""
import argparse
import logging
import json
import os
import re
import shutil
import subprocess
import tempfile
import yaml

from googleapiclient import discovery
from google.cloud import storage
from kubeflow.testing import util
from retrying import retry
from oauth2client.client import GoogleCredentials

@retry(wait_fixed=60000, stop_max_attempt_number=5)
def run_with_retry(*args, **kwargs):
  util.run(*args, **kwargs)

def delete_storage_deployment(project, name):
  credentials = GoogleCredentials.get_application_default()
  dm = discovery.build("deploymentmanager", "v2", credentials=credentials)

  deployments_client = dm.deployments()

  try:
    op = deployments_client.delete(project=project, deployment=name,
                                   deletePolicy="DELETE").execute()
  except Exception as e:
    if hasattr(e, 'content'):
      m = json.loads(e.content)
      if m.get("error", {}).get("code") == 404:
        return
      raise
    raise

  util.wait_for_gcp_operation(dm.operations(), project, None, op["name"])


def create_info_file(args, app_dir, git_describe):
  """Creates an info file in the KF app directory."""
  # This step needs to be called after kfctl init because the directory needs to
  # exist.
  with open(os.path.join(app_dir, "kf_app.yaml"), "w") as hf:
    app = {
      "labels": {
        "GIT_LABEL": git_describe,
        "PURPOSE": "kf-test-cluster",
      },
    }
    if args.job_name:
      app["labels"]["DEPLOYMENT_JOB"] = args.job_name
    yaml.dump(app, hf)

def deploy_with_kfctl_sh(args, app_dir, env):
  """Deploy Kubeflow using kfctl.sh."""
  kfctl = os.path.join(args.kubeflow_repo, "scripts", "kfctl.sh")
  name = os.path.basename(app_dir)
  util.run([kfctl, "init", name, "--project", args.project, "--zone", args.zone,
            "--platform", "gcp", "--skipInitProject", "true"], cwd=args.apps_dir
           )
  # We need to apply platform before doing generate k8s because we need
  # to have a cluster for ksonnet.
  # kfctl apply all might break during cronjob invocation when depending
  # components are not ready. Make it retry several times should be enough.
  run_with_retry([kfctl, "generate", "platform"], cwd=app_dir, env=env)
  run_with_retry([kfctl, "apply", "platform"], cwd=app_dir, env=env)
  run_with_retry([kfctl, "generate", "k8s"], cwd=app_dir, env=env)
  run_with_retry([kfctl, "apply", "k8s"], cwd=app_dir, env=env)
  run_with_retry(["ks", "generate", "seldon", "seldon"], cwd=app_dir,
                  env=env)

def build_kfctl_go(args):
  """Build kfctl go."""
  build_dir = os.path.join(args.kubeflow_repo, "bootstrap")
  # We need to use retry builds because when building in the test cluster
  # we see intermittent failures pulling dependencies
  util.run(["make", "build-kfctl"], cwd=build_dir)
  kfctl_path = os.path.join(build_dir, "bin", "kfctl")

  return kfctl_path

def deploy_with_kfctl_go(kfctl_path, args, app_dir, env):
  """Deploy Kubeflow using kfctl go binary."""
  # username and password are passed as env vars and won't appear in the logs
  #
  # TODO(https://github.com/kubeflow/kubeflow/issues/2831): We should be
  # loading the config in the repo we have checked out kfctl doesn't support
  # specifying a file URI. Once it does we should change --version to
  # use it.
  #
  # TODO(zhenghuiwang): use the master of kubeflow/manifests once
  # https://github.com/kubeflow/kubeflow/issues/3475 is fixed.
  logging.warning("Loading configs from master.")
  util.run([kfctl_path, "init", app_dir, "-V", "--platform=gcp",
            "--version=master",
            "--package-manager=kustomize@1e6b55258c678c6b151ea17a039acf6170706a23",
            "--skip-init-gcp-project",
            "--disable_usage_report",
            "--use_istio",
            "--project=" + args.project], env=env)

  # We need to specify a valid email because
  #  1. We need to create appropriate RBAC rules to allow the current user
  #     to create the required K8s resources.
  #  2. Setting the IAM policy will fail if the email is invalid.
  # TODO(jlewi): kfctl should eventually do this automatically.
  email = util.run(["gcloud", "config", "get-value", "account"])

  if not email:
    raise ValueError("Could not determine GCP account being used.")

  util.run([kfctl_path, "generate", "-V", "all", "--email=" + email,
            "--zone=" + args.zone], env=env, cwd=app_dir)

  util.run([kfctl_path, "apply", "-V", "all"], env=env, cwd=app_dir)

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
    default="/home/jlewi/git_kubeflow",
    type=str, help=("Path to the Kubeflow repo to use"))

  parser.add_argument(
    "--apps_dir",
    default=os.getcwd(),
    type=str, help=("Directory to store kubeflow apps."))

  parser.add_argument(
    "--name", type=str, default="", help=("Name for the deployment."))

  parser.add_argument(
    "--snapshot_file",
    default="", type=str, help=("A json file containing information about the "
                                "snapshot to use."))

  parser.add_argument(
    "--job_name",
    default="", type=str, help=("Pod name running the job."))

  parser.add_argument(
    "--use_kfctl_go", dest="use_kfctl_go", action="store_true",
    help=("Use the go binary."))

  parser.add_argument(
    "--no-use_kfctl_go", dest="use_kfctl_go", action="store_false",
    help=("Use kfctl.sh."))

  parser.set_defaults(use_kfctl_go=True)
  args = parser.parse_args()

  bucket, blob_path = util.split_gcs_uri(args.oauth_file)

  client = storage.Client(project=args.project)
  bucket = client.get_bucket(bucket)

  blob = bucket.get_blob(blob_path)
  contents = blob.download_as_string()

  oauth_info = yaml.load(contents)

  git_describe = util.run(["git", "describe", "--tags", "--always", "--dirty"],
                          cwd=args.kubeflow_repo).strip("'")

  if args.snapshot_file:
    logging.info("Loading info from snapshot file %s", args.snapshot_file)
    with open(args.snapshot_file) as hf:
      snapshot_info = json.load(hf)
      name = snapshot_info["name"]
  else:
    name = args.name

  kfctl_path = None
  if args.use_kfctl_go:
    kfctl_path = build_kfctl_go(args)


  app_dir = os.path.join(args.apps_dir, name)
  # Clean up previous deployment. We attempt to run "kfctl delete all"
  # but we don't depend on it succeeding because the app directory might
  # not be up to date.
  # since we are not able to guarantee apps config in repository is up to date.
  if os.path.exists(app_dir) and args.use_kfctl_go:
    try:
      util.run([kfctl_path, "delete", "all", "--delete_storage"], cwd=app_dir)
    except subprocess.CalledProcessError as e:
      logging.error("kfctl delete all failed; %s", e)

  if os.path.exists(app_dir):
    shutil.rmtree(app_dir)

  if not os.path.exists(args.apps_dir):
    os.makedirs(args.apps_dir)

  # Delete deployment beforehand. If not, updating action might be failed when
  # resource permission/requirement is changed. It's cleaner to delete and
  # re-create it.
  delete_deployment = os.path.join(args.kubeflow_repo, "scripts", "gke",
                                   "delete_deployment.sh")

  util.run([delete_deployment, "--project=" + args.project,
            "--deployment=" + name, "--zone=" + args.zone], cwd=args.apps_dir)

  # Delete script doesn't delete storage deployment by design.
  delete_storage_deployment(args.project, name + "-storage")

  env = {}
  env.update(os.environ)
  env.update(oauth_info)

  labels = {
    "GIT_LABEL": git_describe,
    "PURPOSE": "kf-test-cluster",
    "use-kfctl-go": "{0}".format(args.use_kfctl_go),
  }

  label_args = []
  for k, v in labels.items():
    # labels can only take as input alphanumeric characters, hyphens, and
    # underscores. Replace not valid characters with hyphens.
    val = v.lower().replace("\"", "")
    val = re.sub(r"[^a-z0-9\-_]", "-", val)
    label_args.append("{key}={val}".format(key=k.lower(), val=val))

  endpoint = "{name}.endpoints.{project}.cloud.goog".format(
      name=name,
      project=args.project)
  # Fire-and-forgot process to undelete endpoint services. Deletion to
  # endpoint service is soft-deletion, e.g. it will be purged after 30
  # days. If any deployments is trying to re-use the same endpoint, it
  # will be an error if it's in soft-deletion. Need to undelete it so
  # that endpoint-controller could complete its job.
  try:
    util.run(["gcloud", "endpoints", "services", "undelete", endpoint,
              "--verbosity=info", "--project="+args.project])
  except subprocess.CalledProcessError as e:
    logging.info("endpoint undeletion is failed: %s", e)

  if args.use_kfctl_go:
    deploy_with_kfctl_go(kfctl_path, args, app_dir, env)
  else:
    deploy_with_kfctl_sh(args, app_dir, env)

  create_info_file(args, app_dir, git_describe)
  logging.info("Annotating cluster with labels: %s", str(label_args))

  # Set labels on the deployment
  util.run(["gcloud", "--project", args.project,
            "deployment-manager", "deployments", "update", name,
            "--update-labels", ",".join(label_args)],
            cwd=app_dir)

  # Set labels on the cluster. Labels on the deployment is not shown on
  # Pantheon - it's easier for users to read if cluster also has labels.
  util.run(["gcloud", "container", "clusters", "update", name,
            "--project", args.project,
            "--zone", args.zone,
            "--update-labels", ",".join(label_args)],
           cwd=app_dir)

  # To work around lets-encrypt certificate uses create a self-signed
  # certificate
  util.run(["kubectl", "config", "use-context", name])
  tls_endpoint = "--host={0}.endpoints.{1}.cloud.goog".format(
    name, args.project)

  cert_dir = tempfile.mkdtemp()
  util.run(["kube-rsa", tls_endpoint], cwd=cert_dir)
  util.run(["kubectl", "-n", "kubeflow", "create", "secret", "tls",
            "envoy-ingress-tls", "--cert=ca.pem", "--key=ca-key.pem"],
            cwd=cert_dir)
  shutil.rmtree(cert_dir)

if __name__ == "__main__":
  main()
