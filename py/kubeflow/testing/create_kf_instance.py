"""Create a Kubeflow instance.

The purpose of this script is to automate the creation of Kubeflow Deployments
corresponding to different versions of Kubeflow.
"""
import argparse
import logging
import os
import re
import yaml

from google.cloud import storage
from kubeflow.testing import util
from retrying import retry

@retry(wait_fixed=60000, stop_max_attempt_number=5)
def kfctl_apply_with_retry(kfctl, cwd, env):
  util.run([kfctl, "apply", "all"], cwd=cwd, env=env)

def set_TLS(cluster):
  github_kube_rsa = "github.com/kelseyhightower/kube-rsa"
  util.run(["go", "get", github_kube_rsa])
  kube_rsa = "/root/go/bin/kube-rsa"
  tls_endpoint = "--host=%s.endpoints.kubeflow-ci.cloud.goog" % cluster
  util.run([kube_rsa, tls_endpoint])


def main(): # pylint: disable=too-many-locals,too-many-statements
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)

  parser = argparse.ArgumentParser()

  parser.add_argument(
    "--base_name", default="kf-v0-4", type=str,
    help=("The base name for the deployment typically kf-vX-Y or kf-vmaster."))

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
    "--deployment_worker_cluster",
    default="kubeflow-testing",
    type=str, help=("Name of cluster deployment cronjob workers use."))

  parser.add_argument(
    "--cluster_num",
    default="", type=int, help=("Number of cluster to deploy to."))

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

  # TODO(https://github.com/kubeflow/testing/issues/95): We want to cycle
  # between N different names e.g.
  # kf-vX-Y-n00, kf-vX-Y-n01, ... kf-vX-Y-n05
  # The reason to reuse names is because for IAP we need to manually
  # set the redirect URIs. So we want to cycle between a set of known
  # endpoints. We should add logic to automatically recycle deployments.
  # i.e. we should find the oldest one and reuse that.
  num = args.cluster_num
  name = "{0}-n{1:02d}".format(args.base_name, num)
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

  # Create a dummy kubeconfig in cronjob worker.
  util.run(["gcloud", "container", "clusters", "get-credentials", args.deployment_worker_cluster,
            "--zone", args.zone, "--project", args.project], cwd=args.apps_dir)

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
    if args.timestamp:
      app["labels"]["SNAPSHOT_TIMESTAMP"] = args.timestamp
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

  util.run([kfctl, "generate", "all"], cwd=app_dir)
  util.run(["ks", "generate", "seldon", "seldon"], cwd=ks_app_dir)

  env = {}
  env.update(os.environ)
  env.update(oauth_info)
  # kfctl apply all might break during cronjob invocation when depending
  # components are not ready. Make it retry several times should be enough.
  kfctl_apply_with_retry(kfctl, app_dir, env)

  logging.info("Annotating cluster with labels: %s", str(label_args))
  util.run(["gcloud", "container", "clusters", "update", name,
            "--zone", args.zone,
            "--update-labels", ",".join(label_args)],
           cwd=app_dir)
  util.run(["gcloud", "container", "clusters", "get-credentials", name,
            "--zone", args.zone,
            "--protject", args.project])
  set_TLS(name)
  util.run(["kubectl", "-n", "kubeflow", "create", "secret", "tls",
           "envoy-ingress-tls", "--cert=ca.pem", "--key=ca-key.pem"])

if __name__ == "__main__":
  main()
