from __future__ import print_function

import unittest

from kubeflow.testing import cleanup_ci
import os
import yaml

class CleanupCiTest(unittest.TestCase):
  def setUp(self):
    self.test_dir = os.path.join(os.path.dirname(__file__), "test-data")

  def test_wait_for_workflow(self):
    with open(os.path.join(self.test_dir, "iam_bindings.yaml")) as bd:
      iam_bindings = yaml.load(bd)
      self.assertTrue(len(iam_bindings['bindings']) == 3)
      members = iam_bindings['bindings'][0]['members']
      for act in ['my-other-app@appspot.gserviceaccount.com',
                  'kfctl-in-use@kubeflow-ci.iam.gserviceaccount.com',
                  'kfctl-expired@kubeflow-ci.iam.gserviceaccount.com']:
        self.assertTrue('serviceAccount:' + act in members)
      cleanup_ci.trim_unused_bindings(iam_bindings,
                                      ['kfctl-in-use@kubeflow-ci.iam.gserviceaccount.com'])
      # One binding is deleted as it lost all members.
      self.assertTrue(len(iam_bindings['bindings']) == 2)
      trimed_members = iam_bindings['bindings'][0]['members']
      # binding to non-match service account still exists as it is not created by ci tests.
      self.assertTrue(
        'serviceAccount:my-other-app@appspot.gserviceaccount.com'in trimed_members)
      # binding to existing service account still exists.
      self.assertTrue(
        'serviceAccount:kfctl-in-use@kubeflow-ci.iam.gserviceaccount.com' in trimed_members)
      # binding to unexist service account is deleted.
      self.assertTrue(
        'serviceAccount:kfctl-expired@kubeflow-ci.iam.gserviceaccount.com' not in trimed_members)

if __name__ == "__main__":
  unittest.main()
