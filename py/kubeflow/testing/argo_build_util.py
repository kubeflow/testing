"""Utilities for building argo workflows in python."""

import six
import os
import yaml

if six.PY3:
  from urllib.parse import urlencode
else:
  import urllib

def get_prow_dict():
  # see https://github.com/kubernetes/test-infra/blob/70015225876afea36de3ce98f36fe1592e8c2e53/prow/jobs.md  # pylint: disable=line-too-long
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
  # see https://github.com/kubernetes/test-infra/blob/70015225876afea36de3ce98f36fe1592e8c2e53/prow/jobs.md # pylint: disable=line-too-long
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

  for k, v in get_prow_labels().items():
    spec["metadata"]["labels"][k] = v
  return spec

def deep_copy(d):
  """Perform a deep copy of the supplied object"""
  s = yaml.dump(d)
  return yaml.load(s)

def add_task_only_to_dag(workflow, dag_name, task_name, template_name,
                         dependencies):
  """Add a task but do not create a template in the dag.

  Args:
    workflow: The Argo workflow.
    dag_name: The name of the dag.
    task_name: Name to give the task
    template_name: Name of the template to use
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

  new_task = {
    "name": task_name,
    "template": template_name,
  }

  dag["dag"]["tasks"].append(new_task)
  if dependencies:
    new_task["dependencies"] = dependencies

# TODO(jlewi): We should rename this function to something that
# better captures the fact that we are adding a task and template
# simultaneously. Maybe just add_template_to_dag?
# templates aren't stored in dag so arguable that implies that we
# are also creating a step in the dag. Should we also have methods
# add_task_to_dag and add_template and then this would just be a wrapper
# around those two methods?
def add_task_to_dag(workflow, dag_name, task, dependencies):
  """Add a task to the specified workflow.

  Create a template and a task referencing that template.

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

  new_task = {
    "name": task["name"],
    "template": task["name"],
  }

  if dependencies:
    new_task["dependencies"] = dependencies

  dag["dag"]["tasks"].append(new_task)

  new_template = deep_copy(task)

  if "name" not in new_template:
    raise ValueError("Task template is missing name")

  if not new_template["name"]:
    raise ValueError("Task template name can't be empty string")

  workflow["spec"]["templates"].append(new_template)

def set_task_template_labels(workflow):
  """Automatically set the labels and annotations on each step.

  Args:
   workflow: Workflow to set the labels.

  Returns:
   workflow: Workflow with labels set on all the steps.

  Labels on template steps are set as follows
    1. Labels on the workflow are copied to each step template
    2. Each step gets added labels with the step_name and the workflow name

  Annotations are set on each step as follows
    1. Add a link to stackdriver for each step
  """

  name = workflow["metadata"].get("name")
  labels = workflow["metadata"].get("labels")

  for t in workflow["spec"]["templates"]:
    if not "container" in t:
      continue

    if not "metadata" in t:
      t["metadata"] = {}

    if not "labels" in t["metadata"]:
      t["metadata"]["labels"] = {}

    if not "annotations" in t["metadata"]:
      t["metadata"]["annotations"] = {}

    # Store in the annotations a stackdriver link for the step.
    t["metadata"]["annotations"]["kubeflow.org/logs"] = logs_link_for_step(
      name, t["name"])
    t["metadata"]["labels"].update(labels)
    t["metadata"]["labels"]["step_name"] = t["name"]
    t["metadata"]["labels"]["workflow"] = name

  return workflow

def add_dicts(dicts):
  """Combine a list of dictionaries and return the results.
  Args:
    dicts: List of dicts

  Returns:
    d: Combined dict
  """
  n = {}

  for d in dicts:
    n.update(d)

  return n

def get_repo_from_prow_env():
  """Returns the repo spec based on prow_env

  Args:
    repo: A string of the form ${REPO_OWNER}/${REPO_NAME}@HEAD:{PULLNUMBER} or
      ${REPO_OWNER}/${REPO_NAME}@branch. The value is based on prow env.
      Returns None if prow environment variables aren't set.
      The returned string is compatible with checkout_repo.sh
  """
  # see https://github.com/kubernetes/test-infra/blob/70015225876afea36de3ce98f36fe1592e8c2e53/prow/jobs.md  # pylint: disable=line-too-long
  if not os.getenv("REPO_OWNER") or not os.getenv("REPO_NAME"):
    return None

  repo_owner = os.getenv("REPO_OWNER")
  repo_name = os.getenv("REPO_NAME")

  job_type = os.getenv("JOB_TYPE", "").lower()
  if  job_type == "presubmit":
    version = "{0}:{1}".format(
      os.getenv("PULL_PULL_SHA", "HEAD"), os.getenv("PULL_NUMBER"))
  elif job_type == "postsubmit":
    version = "{0}".format(os.getenv("PULL_BASE_SHA"))
  else:
    branch = os.getenv("BRANCH_NAME", "HEAD")
    version = "{0}".format(branch)

  return "{0}/{1}@{2}".format(repo_owner, repo_name, version)

def logs_link_for_step(workflow, step, project="kubeflow-ci"):
  """Return the stackdriver link for the specified step in the workflow.

  Args:
    workflow: Name of the workflwo
    step: Name of the step
    project: Project the wokflow ran in.
  """
  logs_filter = """resource.type="k8s_container"
metadata.userLabels.step_name="{step}"
metadata.userLabels."workflows.argoproj.io/workflow"="{workflow}"
resource.labels.container_name="main"\n""".format(workflow=workflow, step=step)

  new_params = {'project': project,
               # Logs for last 7 days
               'interval': 'P7D',
               'advancedFilter': logs_filter}


  if six.PY3:
    query = urlencode(new_params)
  else:
    query = urllib.urlencode(new_params)

  url = "https://console.cloud.google.com/logs/viewer?" + query

  return url
