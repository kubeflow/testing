
import logging
import os
import pytest

from kubeflow.testing.auto_deploy import blueprint_reconciler

def test_pipeline_wrapper():
  test_dir = os.path.join(os.path.dirname(__file__), "test_data")

  pipeline_file = os.path.join(test_dir, "example-pipeline-run.yaml")

  run = blueprint_reconciler.PipelineRunWrapper.from_file(pipeline_file)

  assert run.base_name == "kf-vbp"
  assert run.group == "gcp-blueprint-master"
  assert (run.get_resource_param("blueprint-repo", "url") ==
          "https://github.com/jlewi/gcp-blueprints.git")

  run.set_resource_param("blueprint-repo", "url", "newurl")
  assert (run.get_resource_param("blueprint-repo", "url") ==
          "newurl")

  assert run.get_param("name") == "somename"
  run.set_param("name", "newname")
  assert run.get_param("name") == "newname"

if __name__ == "__main__":
  logging.basicConfig(
      level=logging.INFO,
      format=('%(levelname)s|%(asctime)s'
            '|%(pathname)s|%(lineno)d| %(message)s'),
    datefmt='%Y-%m-%dT%H:%M:%S',
    )
  logging.getLogger().setLevel(logging.INFO)

  pytest.main()
