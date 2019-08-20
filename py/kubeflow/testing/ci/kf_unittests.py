"""Test Argo workflow"""

import requests
import yaml

def create_workflow(**kwargs):
  """ Loads Argo example YAML and returns dictionary object """
  # TODO: define workflow to run unittests
  argo_hello_world = requests.get("https://raw.githubusercontent.com/argoproj/argo/master/examples/hello-world.yaml")
  yaml_result = yaml.safe_load(argo_hello_world.text)
  return yaml_result

if __name__ == "__main__":
  create_workflow()
