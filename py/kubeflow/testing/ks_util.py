"""Utilities for working with ksonnet in the tests."""

import filelock
import logging
import os
import re
import subprocess
import yaml

from kubeflow.testing import util

def setup_ks_app(app_dir, env, namespace, component, params, ks_cmd=None):
  """Setup the ksonnet app"""

  if not ks_cmd:
    ks_cmd = get_ksonnet_cmd(app_dir)

  lock_file = os.path.join(app_dir, "app.lock")
  logging.info("Acquiring lock on file: %s", lock_file)
  lock = filelock.FileLock(lock_file, timeout=60)
  with lock:
    # Create a new environment for this run
    try:
      util.run([ks_cmd, "env", "add", env, "--namespace=" + namespace],
                cwd=app_dir)
    except subprocess.CalledProcessError as e:
      if not re.search(".*environment.*already exists.*", e.output):
        raise

    if params:
      for pair in params.split(","):
        k, v = pair.split("=", 1)
        util.run([ks_cmd, "param", "set", "--env=" + env, component, k, v],
                  cwd=app_dir)

def get_ksonnet_cmd(app_dir):
  """Get the ksonnet command based on the apiVersion in app.yaml.

  Args:
    app_dir: Directory of the ksonnet application.

  Returns:
    ks_cmd: Path to the ks binary to use.
  """
  app_yaml_file = app_dir + "/app.yaml"
  with open(app_yaml_file) as app_yaml:
    results = yaml.load(app_yaml)

  if results["apiVersion"] == "0.1.0":
    return "ks"

  if results["apiVersion"] == "0.2.0":
    return "ks-12"

  if results["apiVersion"] >= "0.3.0":
    return "ks-13"

  # For compatibility reasons we'll keep the default cmd as "ks".
  return "ks"
