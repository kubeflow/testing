"""Utilities for building argo workflows in python."""

import os
import yaml

def get_prow_dict():
  # see https://github.com/kubernetes/test-infra/blob/70015225876afea36de3ce98f36fe1592e8c2e53/prow/jobs.md
  prow_vars = ["JOB_NAME", "JOB_TYPE", "JOB_SPEC", "BUILD_ID", "PROW_JOB_ID",
               "REPO_OWNER", "REPO_NAME", "PULL_BASE_REF", "PULL_REFS",
               "PULL_NUMBER", "PULL_PULL_SHA"]

  d = {}
  for v in prow_vars:
    if not os.getenv(v):
      continue

    d[v] = os.getenv(v)

  return d

def get_prow_labels():
  """Return a dictionary of prow labels suitable for use as labels"""
  # see https://github.com/kubernetes/test-infra/blob/70015225876afea36de3ce98f36fe1592e8c2e53/prow/jobs.md
  prow_vars = ["JOB_NAME", "JOB_TYPE", "BUILD_ID", "PROW_JOB_ID",
               "REPO_OWNER", "REPO_NAME", "PULL_NUMBER"]

  d = {}
  for v in prow_vars:
    if not os.getenv(v):
      continue

    d[v] = os.getenv(v)

  return d

def add_prow_env(spec):
  """Copy any prow environment variables to the step.

  Args:
    spec: Argo template spec

  Returns:
    spec: Updated spec
  """

  if not spec.get("container").get("env"):
    spec["container"]["env"] = []

  prow_dict = get_prow_dict()
  for k, v in prow_dict.items():
    spec["container"]["env"].append({"name": k,
                                     "value": v})

  for k, v in get_prow_labels():
    spec["metadata"]["labels"][k] = v
  return spec

def deep_copy(d):
  """Perform a deep copy of the supplied object"""
  s = yaml.dump(d)
  return yaml.load(s)

def add_task_to_dag(workflow, dag_name, task, dependencies):
  """Add a task to the specified workflow.

  Args:
    workflow: The workflow spec
    dag_name: The name of the dag to add the step to
    task: The task template
    dependencies: A list of dependencies
  """

  dag = None
  for t in workflow["spec"]["templates"]:
    if "dag" not in t:
      continue
    if t["name"] == dag_name:
      dag = t

  if not dag:
    raise ValueError("No dag named {0} found".format(dag_name))

  if not dag["dag"].get("tasks"):
    dag["dag"]["tasks"] = []

  dag["dag"]["tasks"].append(
    {
      "name": task["name"],
      "template": task["name"],
    }
  )

  workflow["spec"]["templates"].append(task)
