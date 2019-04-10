"""Tests for get_kf_testing_cluster."""

import json
import os
import unittest

from googleapiclient.http import HttpMockSequence
from kubeflow.testing import get_kf_testing_cluster

class GetKfTestingClusterTest(unittest.TestCase):
  def setUp(self):
    with open(os.path.join(os.path.dirname(__file__),
                           "test-data",
                           "deploymentmanager-v2.json")) as f:
      self.dm_api = f.read()

  def test_list_deployments_desc_ordered(self):
    deployments = dict({
        'deployments': [
            {
                'name': 'kf-vmaster-n99',
                'labels': [
                    {
                        'purpose': 'kf-test-cluster',
                        'git_label': 'v0-23-g0169963',
                        'testing': 'gabrielwen-test',
                    }
                ],
                'insertTime': '1973-12-31T23:59:59+00:00',
            },
        ],
    })
    http = HttpMockSequence([
        ({'status': '200'}, self.dm_api),
        ({'status': '200'}, json.dumps(deployments)),
    ])
    actual = get_kf_testing_cluster.list_deployments("kubeflow-ci-deployment",
                                                     "kf-vmaster",
                                                     "kf-test-cluster",
                                                     http=http)
    print("test deployments")
    print(actual)


if __name__ == '__main__':
  unittest.main()
