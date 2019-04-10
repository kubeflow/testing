"""Tests for get_kf_testing_cluster."""

import json
import os
import unittest

from googleapiclient.http import HttpMockSequence
from kubeflow.testing import get_kf_testing_cluster

TEST_PROJECT = "kubeflow-ci-foo"
TEST_LABEL = "kf-foo-label"

class Deployment(object):
  def __init__(self, name, insert_time):
    self.name = name
    self.insert_time = insert_time

def create_mock_http_resp(deployments):
  data = []
  for d in deployments:
    data.append({
        "name": d.name,
        "labels": [
            {
                "purpose": TEST_LABEL,
            },
        ],
        "insertTime": d.insert_time,
    })
  return data

def create_expected_list_resp(deployments):
  data = []
  for d in deployments:
    data.append({
        "name": d.name,
        "endpoint": get_kf_testing_cluster.get_deployment_endpoint(TEST_PROJECT, d.name),
        "insertTime": d.insert_time,
    })
  return data

class GetKfTestingClusterTest(unittest.TestCase):
  def setUp(self):
    with open(os.path.join(os.path.dirname(__file__),
                           "test-data",
                           "deploymentmanager-v2.json")) as f:
      self.dm_api = f.read()

  def test_list_deployments(self):
    deployments = [
        Deployment("kf-vfoo-n00", "2019-04-01T23:59:59+00:00"),
        Deployment("kf-vfoo-n01", "2019-04-02T23:59:59+00:00"),
        Deployment("kf-vfoo-n02", "2019-04-03T23:59:59+00:00"),
    ]
    list_resp = {
        "deployments": create_mock_http_resp(deployments),
    }
    http = HttpMockSequence([
        ({'status': '200'}, self.dm_api),
        ({'status': '200'}, json.dumps(list_resp)),
    ])
    actual = get_kf_testing_cluster.list_deployments(TEST_PROJECT,
                                                     "kf-vfoo",
                                                     TEST_LABEL,
                                                     http=http)
    expected = create_expected_resp(deployments)
    self.assertListEqual(actual, expected)


if __name__ == '__main__':
  unittest.main()
