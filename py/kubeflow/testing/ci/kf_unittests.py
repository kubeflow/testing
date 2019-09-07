"""
A smoke test to ensure run_e2e_workflow.py can properly trigger workflows using
a py_func.

This module defines a simple py_func which will return the Argo workflow
resulting from loading the specified YAML file.

The purpose of this is to allow the presubmits/postsubmits to verify that
run_e2e_workflow.py is actually triggering workflows using py_func.
"""

import requests
import yaml

def create_workflow(**kwargs):
  """ Loads Argo example YAML and returns dictionary object """
  # TODO: define workflow to run unittests
  argo_hello_world = requests.get(''.join([v for k, v in kwargs.items()]))
  yaml_result = yaml.safe_load(argo_hello_world.text)
  return yaml_result

if __name__ == "__main__":
  create_workflow()
