"""Create a Kubeflow instance.

The purpose of this script is to automate the creation of Kubeflow Deployments
corresponding to different versions of Kubeflow.
"""
import argparse
import logging
import json
import os
import re
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

  manifests_client = dm.manifests()
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

def main(): # pylint: disable=too-many-locals,too-many-statements
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)

  parser = argparse.ArgumentParser()

  parser.add_argument(
    "--project", default="kubeflow-ci", type=str, help=("The project."))

  parser.add_argument(
    "--zone", default="us-east1-d", type=str, help=("The zone to deploy in."))

  parser.add_argument(
    "--oauth_file",
    default="gs://kubeflow-ci_kf-data/kf-iap-oauth.kubeflow-ci.yaml",
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
    "--name",
    default="", type=str, help=("Name for the deployment."))

  parser.add_argument(
    "--snapshot_file",
    default="", type=str, help=("A json file containing information about the "
                                "snapshot to use."))

  parser.add_argument(
    "--timestamp",
    default="", type=str, help=("Timestamp deployment takes snapshot."))

  parser.add_argument(
    "--job_name",
    default="", type=str, help=("Pod name running the job."))

  args = parser.parse_args()

  bucket, blob_path = util.split_gcs_uri(args.oauth_file)

  client = storage.Client(project=args.project)
  bucket = client.get_bucket(bucket)

  blob = bucket.get_blob(blob_path)
  contents = blob.download_as_string()

  oauth_info = yaml.load(contents)

  git_describe = util.run(["git", "describe", "--tags", "--always", "--dirty"],
                          cwd=args.kubeflow_repo).strip("'")

  timestamp = args.timestamp
  if args.snapshot_file:
    logging.info("Loading info from snapshot file %s", args.snapshot_file)
    with open(args.snapshot_file) as hf:
      snapshot_info = json.load(hf)
      name = snapshot_info["name"]
      timestamp = snapshot_info.get("timestamp", "")
  else:
    name = args.name

  # Clean up previous deployment. We are not able to run "kfctl delete all"
  # since we are not able to guarantee apps config in repository is up to date.
  util.run(["rm", "-rf", name], cwd=args.apps_dir)

  # Delete deployment beforehand. If not, updating action might be failed when
  # resource permission/requirement is changed. It's cleaner to delete and
  # re-create it.
  delete_deployment = os.path.join(args.kubeflow_repo, "scripts", "gke",
                                   "delete_deployment.sh")

  util.run([delete_deployment, "--project=" + args.project,
            "--deployment=" + name, "--zone=" + args.zone], cwd=args.apps_dir)

  # Delete script doesn't delete storage deployment by design.
  delete_storage_deployment(args.project, name + "-storage")

  app_dir = os.path.join(args.apps_dir, name)
  kfctl = os.path.join(args.kubeflow_repo, "scripts", "kfctl.sh")
  ks_app_dir = os.path.join(app_dir, "ks_app")
  util.run([kfctl, "init", name, "--project", args.project, "--zone", args.zone,
            "--platform", "gcp", "--skipInitProject", "true"], cwd=args.apps_dir
           )

  labels = {}
  with open(os.path.join(app_dir, "kf_app.yaml"), "w") as hf:
    app = {
      "labels": {
        "GIT_LABEL": git_describe,
        "PURPOSE": "kf-test-cluster",
      },
    }
    if timestamp:
      app["labels"]["SNAPSHOT_TIMESTAMP"] = timestamp
    if args.job_name:
      app["labels"]["DEPLOYMENT_JOB"] = args.job_name
    labels = app.get("labels", {})
    yaml.dump(app, hf)

  label_args = []
  for k, v in labels.items():
    # labels can only take as input alphanumeric characters, hyphens, and
    # underscores. Replace not valid characters with hyphens.
    val = v.lower().replace("\"", "")
    val = re.sub(r"[^a-z0-9\-_]", "-", val)
    label_args.append("{key}={val}".format(key=k.lower(), val=val))


  env = {}
  env.update(os.environ)
  env.update(oauth_info)

  # We need to apply platform before doing generate k8s because we need
  # to have a cluster for ksonnet.
  # kfctl apply all might break during cronjob invocation when depending
  # components are not ready. Make it retry several times should be enough.
  run_with_retry([kfctl, "generate", "platform"], cwd=app_dir, env=env)
  run_with_retry([kfctl, "apply", "platform"], cwd=app_dir, env=env)
  run_with_retry([kfctl, "generate", "k8s"], cwd=app_dir, env=env)
  run_with_retry([kfctl, "apply", "k8s"], cwd=app_dir, env=env)
  run_with_retry(["ks", "generate", "seldon", "seldon"], cwd=ks_app_dir, env=env)

  logging.info("Annotating cluster with labels: %s", str(label_args))

  # Set labels on the deployment
  util.run(["gcloud", "--project", args.project,
            "deployment-manager", "deployments", "update", name,
            "--update-labels", ",".join(label_args)],
            cwd=app_dir)

  # To work around lets-encrypt certificate uses create a self-signed
  # certificate
  util.run(["gcloud", "container", "clusters", "get-credentials", name,
            "--zone", args.zone,
            "--project", args.project])
  tls_endpoint = "--host=%s.endpoints.kubeflow-ci.cloud.goog" % name
  util.run(["kube-rsa", tls_endpoint])
  util.run(["kubectl", "-n", "kubeflow", "create", "secret", "tls",
           "envoy-ingress-tls", "--cert=ca.pem", "--key=ca-key.pem"])

if __name__ == "__main__":
  main()
