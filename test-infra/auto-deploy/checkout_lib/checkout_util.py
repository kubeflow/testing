"""Utility function for repositories checkout.
"""

import os
import re

JOB_NAME_REGEX = re.compile("job-name=\"([a-z0-9-]+)\"")

def find_job_name(line):
  """Find job name from labels.

  Args:
    line: str. A line in labels file from Downward API.

  Returns:
    job_name: Job name from labels.
  """
  job_name = JOB_NAME_REGEX.match(line)
  return job_name.group(1) if job_name and job_name.group(1) else ""

def get_job_name(label_file):
  """Extract job name from Downward API label file.

  Args:
    label_file: str. Path to label file mounted from API.

  Returns:
    job_name: Job name from labels.

  Raises:
    RuntimeError if job name is not found from the file.
  """
  labels = open(label_file, "r")
  for line in labels.readlines():
    job_name = find_job_name(line)
    if job_name:
      return job_name
  raise RuntimeError("Not able to find job_name from labels.")

# TODO(jlewi): I don't think we need this anymore
# We should now be using the downward API to set a unique directory based
# on the pod name.
def get_snapshot_path(nfs_path, job_name):
  """Helper function to format folder path for snapshots given mounted NFS path
  and job name.

  Args:
    nfs_path: NFS mounted path.
    job_name: Job name running this pod.

  Returns:
    path: str. Path to read/write snapshot files.
  """
  return os.path.join(nfs_path, "deployment-snapshot/runs", job_name)
