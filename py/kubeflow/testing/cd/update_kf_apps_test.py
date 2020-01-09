import collections
import difflib
import logging
import os
import pprint
import yaml

from kubeflow.testing.cd import update_kf_apps # pylint: disable=no-name-in-module

import pytest

def test_build_run():
  this_dir = os.path.dirname(__file__)
  template_file = os.path.abspath(os.path.join(this_dir, "..", "..", "..", "..",
                                               "apps-cd", "runs",
                                               "app-pipeline.template.yaml"))

  with open(template_file) as hf:
    template = yaml.load(hf)

  app_spec = """
name: notebook-controller
params:
- name: "path_to_context"
  value: "components/notebook-controller"
- name: "path_to_docker_file"
  value: "components/notebook-controller/Dockerfile"
- name: "path_to_manifests_dir"
  value: "jupyter/notebook-controller"
- name: "src_image_url"
  value: "gcr.io/kubeflow-images-public/notebook-controller"
# The name of the repo containing the source
sourceRepo: kubeflow
"""

  app = yaml.load(app_spec)
  version_spec = """
name: master
# A tag to prefix image names with
tag: vmaster
repos:
  - name: kubeflow
    resourceSpec:
      type: git
      params:
        - name: revision
          value: master
        - name: url
          value: git@github.com:kubeflow/kubeflow.git
  - name: manifests
    resourceSpec:
      type: git
      params:
        - name: revision
          value: master
        - name: url
          value: git@github.com:kubeflow/manifests.git
"""
  version = yaml.load(version_spec)
  commit = "1234abcd"
  run = update_kf_apps._build_run(template, app, version, commit) # pylint: disable=protected-access

  with open(os.path.join("test_data", "notebook_controller.expected.yaml")) as hf:
    expected = yaml.load(hf)

  # Compare yaml dumps
  # TODO(jlewi): Do we need a custom dump
  actual_str = yaml.dump(run)
  actual_lines = actual_str.splitlines()
  expected_str = yaml.dump(expected)
  expected_lines = expected_str.splitlines()

  d = difflib.Differ()
  result = d.compare(expected_lines, actual_lines)
  line_diff = list(result)
  message = pprint.pformat(line_diff)
  assert actual_str == expected_str, message

def test_parse_git_url():
  result = update_kf_apps._parse_git_url("git@github.com:kubeflow/manifests.git") # pylint: disable=protected-access

  assert result == update_kf_apps.GIT_TUPLE("git@github.com", "kubeflow",
                                            "manifests")

def test_get_image():
  kustomize_yaml = """
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
- deployment.yaml
images:
- name: gcr.io/old/image1
  newName: gcr.io/new/image1
  newTag: someTag
- digest: sha256:1234abcd
  name: gcr.io/old/image2
  newName: gcr.io/new/image2:someTag
- digest: sha256:1234abcd
  name: gcr.io/old/image3
  newName: gcr.io/new/image3
"""
  config = yaml.load(kustomize_yaml)

  test_case = collections.namedtuple("testcase", ("image_name", "expected"))

  cases = [test_case("gcr.io/old/image1",
                     update_kf_apps.IMAGE_TUPLE("gcr.io/new/image1", "someTag",
                                                "")),
           test_case("gcr.io/old/image2",
                     update_kf_apps.IMAGE_TUPLE("gcr.io/new/image2", "someTag",
                                                "sha256:1234abcd")),
           test_case("gcr.io/old/image3",
                     update_kf_apps.IMAGE_TUPLE("gcr.io/new/image3", "",
                                                "sha256:1234abcd")),]

  for c in cases:
    actual = update_kf_apps._get_image(config, c.image_name)
    assert c.expected == actual

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  # DO NOT SUBMIT
  test_get_image()
  #pytest.main()
