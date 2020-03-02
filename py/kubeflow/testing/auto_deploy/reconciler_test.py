
import collections
import json
import logging
import os
import pytest
from unittest import mock
import yaml

from kubeflow.testing import assertions
from kubeflow.testing.auto_deploy import reconciler
from kubeflow.testing.auto_deploy import util as auto_deploy_util
from kubernetes import client as k8s_client

class Response(object):
  def __init__(self, data):
    self.data = data

@mock.patch("kubeflow.testing.auto_deploy.reconciler.Reconciler"
            "._get_deployment_zone")
def test_get_deployments(mock_zone):
  mock_zone.return_value = "us-central1-a"

  test_dir = os.path.join(os.path.dirname(__file__), "test_data")

  with open(os.path.join(test_dir, "deployments.yaml")) as hf:
    deployments = yaml.load(hf)

  dm_reconciler = reconciler.Reconciler()

  dm_reconciler._get_deployments(deployments=deployments) # pylint: disable=protected-access

  vmaster = [auto_deploy_util.AutoDeployment(deployment_name="kf-vmaster-0126-1c1",
                            manifests_branch="master",
                            create_time="2020-01-26 04:04:19.267000-08:00"),
             auto_deploy_util.AutoDeployment(deployment_name="kf-vmaster-0127-502",
                            manifests_branch="master",
                            create_time="2020-01-26 16:04:13.855000-08:00"),
             auto_deploy_util.AutoDeployment(deployment_name="kf-vmaster-0127-082",
                            manifests_branch="master",
                            create_time="2020-01-27 04:15:52.111000-08:00"),
             ]
  expected = {
    "vmaster": vmaster,
  }
  assertions.assert_dicts_equal(dm_reconciler._deployments, expected)# pylint: disable=protected-access

def test_job_complete():
  test_dir = os.path.join(os.path.dirname(__file__), "test_data")

  with open(os.path.join(test_dir, "completed_job.yaml")) as hf:
    job = yaml.load(hf)


  client = k8s_client.ApiClient()
  j = client.deserialize(Response(json.dumps(job)), k8s_client.V1Job)
  assert(not reconciler._job_is_running(j)) # pylint: disable=protected-access

def test_parse_kfdef_url():
  test_case = collections.namedtuple("test_case", ("url", "expected"))

  cases = [
    test_case("https://raw.githubusercontent.com/kubeflow/"
              "manifests/master/kfdef/kfctl_gcp_iap.yaml",
              reconciler.KFDEF_URL_TUPLE("raw.githubusercontent.com",
                                         "kubeflow", "manifests",
                                         "master",
                                         "kfdef/kfctl_gcp_iap.yaml"))
  ]

  for c in cases:
    actual = reconciler._parse_kfdef_url(c.url) # pylint: disable=protected-access
    assert actual == c.expected

if __name__ == "__main__":
  logging.basicConfig(
      level=logging.INFO,
      format=('%(levelname)s|%(asctime)s'
            '|%(pathname)s|%(lineno)d| %(message)s'),
    datefmt='%Y-%m-%dT%H:%M:%S',
    )
  logging.getLogger().setLevel(logging.INFO)

  pytest.main()
