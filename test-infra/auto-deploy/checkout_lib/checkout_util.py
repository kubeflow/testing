"""TODO(gabrielwen): DO NOT SUBMIT without one-line documentation for checkout-util.

TODO(gabrielwen): DO NOT SUBMIT without a detailed description of checkout-util.
"""

import os
import re

JOB_NAME_REGEX = re.compile("job-name=\"([a-z0-9-]+)\"")

def find_job_name(line):
  job_name = JOB_NAME_REGEX.match(line)
  return job_name.group(1) if job_name and job_name.group(1) else ""

def get_job_name(label_file):
  labels = open(label_file, "r")
  for line in labels.readlines():
    job_name = find_job_name(line)
    if job_name:
      return job_name
  raise RuntimeError("Not able to find job_name from labels.")

def get_snapshot_path(nfs_path, job_name):
  return os.path.join(nfs_path, "deployment-snapshot/runs", job_name)
