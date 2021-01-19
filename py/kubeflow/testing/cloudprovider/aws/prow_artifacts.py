"""Script to create artifacts needed by Gubernator.

For reference see:
https://github.com/kubernetes/test-infra/tree/master/gubernator
"""
import argparse
import logging
import json
import os
import six
import time
from kubeflow.testing import test_util
import boto3

from kubeflow.testing.cloudprovider.aws import util as aws_util


def create_started(ui_urls):
  """Return a string containing the contents of started.json for gubernator.

  ui_urls: Dictionary of workflow name to URL corresponding to the Argo UI
      for the workflows launched.
  """
  # See:
  # https://github.com/kubernetes/test-infra/tree/master/gubernator#job-artifact-gcs-layout
  # For a list of fields expected by gubernator
  started = {
      "timestamp": int(time.time()),
      "repos": {
      },
      "metadata": {
      },
  }

  repo_owner = os.getenv("REPO_OWNER", "")
  repo_name = os.getenv("REPO_NAME", "")

  if repo_owner:
    sha = os.getenv("PULL_PULL_SHA", "")
    if not sha:
      # Its a post submit job.
      sha = os.getenv("PULL_BASE_SHA", "")

    started["repos"][repo_owner + "/" + repo_name] = sha

  PULL_REFS = os.getenv("PULL_REFS", "")
  if PULL_REFS:
    started["pull"] = PULL_REFS

  if six.PY3:
    items = ui_urls.items()
  else:
    items = ui_urls.iteritems()

  for n, v in items:
    started["metadata"][n + "-ui"] = v
  return json.dumps(started)


def create_finished(success, workflow_phase, ui_urls):
  """Create a string containing the contents for finished.json.

  Args:
    success: Bool indicating whether the workflow succeeded or not.
    workflow_phase: Dictionary of workflow name to phase.
    ui_urls: Dictionary of workflow name to URL corresponding to the Argo UI
      for the workflows launched.
  """
  if success:
    result = "SUCCESS"
  else:
    result = "FAILED"
  finished = {
      "timestamp": int(time.time()),
      "result": result,
      # Dictionary of extra key value pairs to display to the user.
      # TODO(jlewi): Perhaps we should add the GCR path of the Docker image
      # we are running in. We'd have to plumb this in from bootstrap.
      "metadata": {
      },
  }
  # kettle (https://github.com/kubernetes/test-infra/tree/master/kettle) expexts
  # to get commit information in finished["metadata"]["repos"].
  # We leverage kettle to upload kubeflow test logs into bigquery.
  PULL_REFS = os.getenv("PULL_REFS", "")
  repo_owner = os.getenv("REPO_OWNER", "")
  repo_name = os.getenv("REPO_NAME", "")
  if repo_owner and PULL_REFS:
    finished["metadata"]["repos"] = {}
    finished["metadata"]["repos"][repo_owner + "/" + repo_name] = PULL_REFS

  names = set()
  names.update(workflow_phase.keys())
  names.update(ui_urls.keys())
  for n in names:
    finished["metadata"][n + "-phase"] = workflow_phase.get(n, "")
    finished["metadata"][n + "-ui"] = ui_urls.get(n, "")
  return json.dumps(finished)


def create_finished_file_s3(bucket, success, workflow_phase, ui_urls):
  """Create the started file in S3 for gubernator."""
  contents = create_finished(success, workflow_phase, ui_urls)

  target = os.path.join(get_s3_dir(bucket), "finished.json")
  aws_util.upload_to_s3(contents, target, "finished.json")


def get_s3_dir(bucket):
  """Return the s3 directory for this job."""
  pull_number = os.getenv("PULL_NUMBER")
  repo_owner = os.getenv("REPO_OWNER")
  repo_name = os.getenv("REPO_NAME")
  job_name = os.getenv("JOB_NAME")
  job_type = os.getenv("JOB_TYPE")

  # Based on the prow docs the variable is BUILD_ID
  # https://github.com/kubernetes/test-infra/blob/45246b09ed105698aa8fb928b7736d14480def29/prow/jobs.md#job-environment-variables
  # But it looks like the original version of this code was using BUILD_NUMBER.
  # BUILD_NUMBER is now deprecated.
  # https://github.com/kubernetes/test-infra/blob/master/prow/ANNOUNCEMENTS.md
  # In effort to be defensive we try BUILD_ID and fall back to BUILD_NUMBER
  build = os.getenv("BUILD_ID")
  if not build:
    logging.warning("BUILD_ID not set; trying BUILD_NUMBER; BUILD_NUMBER is deprecated")
    build = os.getenv("BUILD_NUMBER")

  if job_type == "presubmit":
    output = ("s3://{bucket}/pr-logs/pull/{owner}_{repo}/"
              "{pull_number}/{job}/{build}").format(
              bucket=bucket,
              owner=repo_owner, repo=repo_name,
              pull_number=pull_number,
              job=os.getenv("JOB_NAME"),
              build=build)
  elif job_type == "postsubmit":
    # It is a postsubmit job
    output = ("s3://{bucket}/logs/{owner}_{repo}/"
              "{job}/{build}").format(
                  bucket=bucket, owner=repo_owner,
                  repo=repo_name, job=job_name,
                  build=build)
  else:
    # Its a periodic job
    output = ("s3://{bucket}/logs/{job}/{build}").format(
        bucket=bucket,
        job=job_name,
        build=build)

  return output


def copy_artifacts_to_s3(args):
  """Sync artifacts to S3."""
  # S3 layout is defined here:
  # Example S3 layout:
  # https://github.com/kubernetes/test-infra/tree/master/gubernator#job-artifact-gcs-layout

  output = get_s3_dir(args.bucket)

  if args.suffix:
    logging.info("Renaming all artifact files to include %s", args.suffix)
    for dirpath, _, files in os.walk(args.artifacts_dir):
      for filename in files:
        full_path = os.path.join(dirpath, filename)

        name, ext = os.path.splitext(filename)
        new_name = "{0}-{1}{2}".format(name, args.suffix, ext)
        new_path = os.path.join(dirpath, new_name)
        logging.info("Rename %s to %s", full_path, new_path)
        os.rename(full_path, new_path)
  aws_util.run(["aws", "s3", "sync", args.artifacts_dir, output])


def create_pr_symlink_s3(args):
  """Create a 'symlink' in S3 pointing at the results for a PR.

  This is a null op if PROW environment variables indicate this is not a PR
  job.
  """
  s3 = boto3.resource('s3')
  # S3 layout is defined here:
  # https://github.com/kubernetes/test-infra/tree/master/gubernator#job-artifact-gcs-layout
  pull_number = os.getenv("PULL_NUMBER")
  if not pull_number:
    # Symlinks are only created for pull requests.
    return

  path = "pr-logs/directory/{job}/{build}.txt".format(
      job=os.getenv("JOB_NAME"), build=os.getenv("BUILD_NUMBER"))

  pull_number = os.getenv("PULL_NUMBER")

  source = aws_util.to_s3_uri(args.bucket, path)
  target = get_s3_dir(args.bucket)
  logging.info("Creating symlink %s pointing to %s", source, target)

  file_name = "{build}.txt".format(build=os.getenv("BUILD_NUMBER"))
  with open(file_name, "w+") as data:
    data.write(target)
  s3.meta.client.upload_file(file_name, args.bucket, path)


def check_no_errors_s3(s3_client, artifacts_dir):
  """Check that all the XML files exist and there were no errors.
  Args:
    s3_client: The S3 client.
    artifacts_dir: The directory where artifacts should be stored.
  Returns:
    True if there were no errors and false otherwise.
  """
  bucket, prefix = aws_util.split_s3_uri(artifacts_dir)
  no_errors = True

  junit_objects = s3_client.list_objects(Bucket=bucket, Prefix=os.path.join(prefix, "junit"))

  if "Contents" not in junit_objects.keys():
    return no_errors

  for b in junit_objects["Contents"]:
    full_path = aws_util.to_s3_uri(bucket, b["Key"])
    if not os.path.splitext(b["Key"])[-1] == ".xml":
      logging.info("Skipping %s; not an xml file", full_path)
      continue
    logging.info("Checking %s", full_path)
    tmp_file = "/tmp/junit.xml"
    s3_client.download_file(bucket, b["Key"], tmp_file)
    with open(tmp_file) as f:
      xml_contents = f.read()

    if test_util.get_num_failures(xml_contents) > 0:
      logging.info("Test failures in %s", full_path)
      no_errors = False

  return no_errors


def finalize_prow_job_to_s3(bucket, workflow_success, workflow_phase, ui_urls):
  """Finalize a prow job.

  Finalizing a PROW job consists of determining the status of the
  prow job by looking at the junit files and then creating finished.json.

  Args
    bucket: The S3 bucket where results are stored.
    workflow_success: Bool indicating whether the job should be considered succeeded or failed.
    workflow_phase: Dictionary of workflow name to phase the workflow is in.
    ui_urls: Dictionary of workflow name to URL corresponding to the Argo UI
      for the workflows launched.
  Returns:
    test_success: Bool indicating whether all tests succeeded.
  """
  # logic for finalizing prow jon to S3
  s3_client = boto3.client("s3")

  output_dir = get_s3_dir(bucket)
  artifacts_dir = os.path.join(output_dir, "artifacts")

  # If the workflow failed then we will mark the prow job as failed.
  # We don't need to check the junit files for test failures because we
  # already know it failed; furthermore we can't rely on the junit files
  # if the workflow didn't succeed because not all junit files might be there.
  test_success = True
  if workflow_success:
    test_success = check_no_errors_s3(s3_client, artifacts_dir)
  else:
    test_success = False

  create_finished_file_s3(bucket, test_success, workflow_phase, ui_urls)

  return test_success

