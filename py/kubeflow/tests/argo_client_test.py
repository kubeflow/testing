from __future__ import print_function

import unittest

from kubeflow.testing import argo_client
import mock
import os
import yaml

class ArgoClientTest(unittest.TestCase):
  def setUp(self):
    self.test_dir = os.path.join(os.path.dirname(__file__), "test-data")

  def test_wait_for_workflow(self):
    with mock.patch("kubeflow.testing.argo_client.k8s_client.ApiClient") as api_client:
      with open(os.path.join(self.test_dir, "successful_workflow.yaml")) as hf:
        response = yaml.load(hf)

      api_client.call_api.return_value = response
      result = argo_client.wait_for_workflow("some-namespace", "some-set")
      self.assertIsNotNone(result)

if __name__ == "__main__":
  unittest.main()
