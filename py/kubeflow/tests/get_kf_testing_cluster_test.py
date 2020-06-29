"""Tests for get_kf_testing_cluster."""

import json
import os
import unittest

from googleapiclient.http import HttpMockSequence
from kubeflow.testing import get_kf_testing_cluster # pylint: disable=no-name-in-module

TEST_PROJECT = "kubeflow-ci-foo"
TEST_LABEL = "kf-foo-label"

class Deployment:
  """Simple data carrier for a deployment."""
  def __init__(self, name, insert_time, zone="us-west1-b"):
    self.name = name
    self.insert_time = insert_time
    self.zone = zone

def create_mock_list_resp(deployments):
  """Given a list of Deployment, transforms into a list of dictionaries as API response"""
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

def create_mock_resource_resp(dm):
  """Given an instance of Deployment, transforms into resource info as API response."""
  return {
      "name": dm.name,
      "insertTime": dm.insert_time,
      "properties": "zone: " + dm.zone,
  }

def create_expected_list_resp(deployments):
  """Helper method to create expected responses from get_kf_testing_cluster.list_deployments"""
  data = []
  for d in deployments:
    data.append({
        "name": d.name,
        "endpoint": get_kf_testing_cluster.get_deployment_endpoint(TEST_PROJECT, d.name),
        "insertTime": d.insert_time,
        "zone": d.zone,
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
        "deployments": create_mock_list_resp(deployments),
    }
    http = HttpMockSequence([
        ({'status': '200'}, self.dm_api),
        ({'status': '200'}, json.dumps(list_resp)),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[0]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[1]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[2]))),
    ])
    actual = get_kf_testing_cluster.list_deployments(TEST_PROJECT,
                                                     "kf-vfoo",
                                                     TEST_LABEL,
                                                     http=http)
    expected = sorted(create_expected_list_resp(deployments),
                      key=lambda entry: entry["insertTime"],
                      reverse=True)
    self.assertListEqual(actual, expected)

  def test_list_deployments_name_filter(self):
    deployments = [
        Deployment("kf-vfoo-n00", "2019-04-01T23:59:59+00:00"),
        Deployment("kf-vfoo-n01", "2019-04-02T23:59:59+00:00"),
        Deployment("kf-vfoo-n02-storage", "2019-04-03T23:59:59+00:00"),
    ]
    list_resp = {
        "deployments": create_mock_list_resp(deployments),
    }
    http = HttpMockSequence([
        ({'status': '200'}, self.dm_api),
        ({'status': '200'}, json.dumps(list_resp)),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[0]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[1]))),
    ])
    actual = get_kf_testing_cluster.list_deployments(TEST_PROJECT,
                                                     "kf-vfoo",
                                                     TEST_LABEL,
                                                     http=http)
    expected = sorted(create_expected_list_resp(deployments[0:2]),
                      key=lambda entry: entry["insertTime"],
                      reverse=True)
    self.assertListEqual(actual, expected)

  def test_list_deployments_default_insertime(self):
    """Verify behavior when one of the deployments is missing a timestamp."""
    deployments = [
        Deployment("kf-vfoo-00", "2019-04-01T23:59:59+00:00"),
        Deployment("kf-vfoo-01", "2019-04-02T23:59:59+00:00"),
        Deployment("kf-vfoo-02", "2019-04-03T23:59:59+00:00"),
    ]
    list_resp = {
        "deployments": create_mock_list_resp(deployments),
    }
    # Remove insertTime for the method to attach default timestamp.
    list_resp["deployments"][-1].pop("insertTime", None)
    http = HttpMockSequence([
        ({'status': '200'}, self.dm_api),
        ({'status': '200'}, json.dumps(list_resp)),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[0]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[1]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[2]))),
    ])
    actual = get_kf_testing_cluster.list_deployments(TEST_PROJECT,
                                                     "kf-vfoo-??",
                                                     TEST_LABEL,
                                                     http=http)
    expected = create_expected_list_resp(deployments)

    # Since the last deployment doesn't have an insertTime it will be ignored
    expected = expected[0:2]

    expected.sort(key=lambda entry: entry["insertTime"],
                  reverse=True)
    self.assertListEqual(actual, expected)

  def test_list_deployments_multi_pages(self):
    deployments = [
        Deployment("kf-vfoo-n00", "2019-04-01T23:59:59+00:00"),
        Deployment("kf-vfoo-n01", "2019-04-02T23:59:59+00:00"),
        Deployment("kf-vfoo-n02", "2019-04-03T23:59:59+00:00"),
    ]
    list_resp1 = {
        "deployments": create_mock_list_resp(deployments[:1]),
        "nextPageToken": "bar",
    }
    list_resp2 = {
        "deployments": create_mock_list_resp(deployments[1:]),
    }
    http = HttpMockSequence([
        ({'status': '200'}, self.dm_api),
        ({'status': '200'}, json.dumps(list_resp1)),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[0]))),
        ({"status": "200"}, json.dumps(list_resp2)),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[1]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[2]))),
    ])
    actual = get_kf_testing_cluster.list_deployments(TEST_PROJECT,
                                                     "kf-vfoo",
                                                     TEST_LABEL,
                                                     http=http)
    expected = sorted(create_expected_list_resp(deployments),
                      key=lambda entry: entry["insertTime"],
                      reverse=True)
    self.assertListEqual(actual, expected)

  def test_get_deployment(self):
    deployments = [
        Deployment("kf-vfoo-n00", "2019-04-01T23:59:59+00:00"),
        Deployment("kf-vfoo-n01", "2019-04-02T23:59:59+00:00"),
        Deployment("kf-vfoo-n02", "2019-04-03T23:59:59+00:00"),
    ]
    list_resp = {
        "deployments": create_mock_list_resp(deployments),
    }
    http = HttpMockSequence([
        ({'status': '200'}, self.dm_api),
        ({'status': '200'}, json.dumps(list_resp)),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[0]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[1]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[2]))),
        ({'status': '200'}, self.dm_api),
        ({'status': '200'}, json.dumps(list_resp)),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[0]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[1]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[2]))),
    ])

    # get latest deployment.
    self.assertEqual(get_kf_testing_cluster.get_deployment(
        TEST_PROJECT,
        "kf-vfoo",
        TEST_LABEL,
        http=http),
                     get_kf_testing_cluster.get_deployment_endpoint(TEST_PROJECT,
                                                                    "kf-vfoo-n02"))
    # get oldest deployment.
    self.assertEqual(get_kf_testing_cluster.get_deployment(
        TEST_PROJECT,
        "kf-vfoo",
        TEST_LABEL,
        http=http,
        desc_ordered=False),
                     get_kf_testing_cluster.get_deployment_endpoint(TEST_PROJECT,
                                                                    "kf-vfoo-n00"))

  def test_get_latest(self):
    deployments = [
        Deployment("kf-vfoo-00", "2019-04-01T23:59:59+00:00"),
        Deployment("kf-vfoo-01", "2019-04-02T23:59:59+00:00"),
        Deployment("kf-vfoo-02", "2019-04-03T23:59:59+00:00"),
    ]
    list_resp = {
        "deployments": create_mock_list_resp(deployments),
    }
    http = HttpMockSequence([
        ({'status': '200'}, self.dm_api),
        ({'status': '200'}, json.dumps(list_resp)),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[0]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[1]))),
        ({"status": "200"}, json.dumps(create_mock_resource_resp(deployments[2]))),
    ])
    self.assertEqual(get_kf_testing_cluster.get_latest(
                     project=TEST_PROJECT, base_name="kf-vfoo-??", http=http),
                     get_kf_testing_cluster.get_deployment_endpoint(TEST_PROJECT,
                                                                    "kf-vfoo-02"))

if __name__ == '__main__':
  unittest.main()
