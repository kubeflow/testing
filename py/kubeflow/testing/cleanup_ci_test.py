import collections
import logging
import os
import pytest
import yaml

from kubeflow.testing import cleanup_ci

class FakeArgs:
  project = "someproject"
  dryrun = True

def assert_lists_equal(left, right):
  message = "Lists are not equal; {0}!={1}".format(left, right)
  assert len(left) == len(right), message

  for i, _ in enumerate(left):
    item_message = (message +
                    "\n; item {0} doesn't match {1}!={2}".format(i, left[i],
                                                                 right[i]))
    assert left[i] == right[i], item_message

def test_auto_deployment_name():
  test_case = collections.namedtuple("test_case", ("name", "expected"))

  test_cases = [
    test_case("kf-vmaster-0126-823",
              cleanup_ci.AutoDeploymentName("kf-vmaster-0126-823", "vmaster")),
    test_case("kf-vmaster-0126-abc",
              cleanup_ci.AutoDeploymentName("kf-vmaster-0126-abc", "vmaster")),
    test_case("kf-vmaster-0126-abc-storage",
              cleanup_ci.AutoDeploymentName("kf-vmaster-0126-abc", "vmaster")),
    test_case("kf-v1-0-0126-abc",
              cleanup_ci.AutoDeploymentName("kf-v1-0-0126-abc", "v1-0")),
    test_case("kf-v1-0-0126-abc-storage",
              cleanup_ci.AutoDeploymentName("kf-v1-0-0126-abc", "v1-0")),
    test_case("kf-invalidname", None),
  ]

  for c in test_cases:
    actual = cleanup_ci.AutoDeploymentName.from_deployment_name(c.name)

    if c.expected is None:
      assert actual is None
    else:
      assert actual == c.expected, "Failed for name={0}".format(c.name)


def test_cleanup_auto_deployments():
  test_dir = os.path.join(os.path.dirname(__file__), "test_data")

  with open(os.path.join(test_dir, "cleanup_deployments.yaml")) as hf:
    deployments = yaml.load(hf)

  to_keep, to_delete = cleanup_ci.cleanup_auto_deployments(
    FakeArgs(), deployments=deployments)

  assert_lists_equal(to_keep, ["kf-vmaster-0128-1ad",
                               "kf-vmaster-0128-12e",
                               "kf-vmaster-0128-03c"])

  expected_delete = [
    "kf-vmaster-0126-1c1", "kf-vmaster-0126-0b5", "kf-vmaster-0126-823",
    "kf-vmaster-0127-502", "kf-vmaster-0127-bf2", "kf-vmaster-0127-c9a",
    "kf-vmaster-0127-83a", "kf-vmaster-0127-082", "kf-vmaster-0127-7e2",
    "kf-vmaster-0128-9d7", "kf-vmaster-0128-54e", "kf-vmaster-0128-ed2"]
  assert_lists_equal(to_delete, expected_delete)

def test_match_endpoints():
  """Verify that cloud endpoint service names match the regex"""

  service_names = [
    "iap-ingress-kfctl-8c9b.endpoints.kubeflow-ci-deployment.cloud.goog",
  ]

  for s in service_names:
    assert cleanup_ci.is_match(s, patterns=cleanup_ci.E2E_PATTERNS)

def test_match_disk():
  pvc = "gke-zresubmit-unittest-pvc-e3bf5be4-987b-11e9-8266-42010a8e00e9"
  assert cleanup_ci.is_match(pvc, patterns=cleanup_ci.E2E_PATTERNS)

def test_match_service_accounts():
  test_case = collections.namedtuple("test_case", ("input", "expected"))

  cases = [
    test_case("kf-vmaster-0121-b11-user@"
              "kubeflow-ci-deployment.iam.gserviceaccount.com",
              cleanup_ci.AUTO_INFRA)
  ]

  for c in cases:
    actual = cleanup_ci.name_to_infra_type(c.input)

    assert actual == c.expected

def test_parse_service_account():
  test_case = collections.namedtuple("test_case", ("input", "expected"))

  cases = [
    test_case("serviceAccount:kf-vmaster@"
              "kubeflow-ci-deployment.iam.gserviceaccount.com",
              cleanup_ci.SERVICE_ACCOUNT("kf-vmaster", "kubeflow-ci-deployment",
                                         "iam.gserviceaccount.com")),
    test_case("serviceAccount:kf-vmaster@"
              "container-engine-robot.iam.gserviceaccount.com",
              cleanup_ci.SERVICE_ACCOUNT("kf-vmaster", "container-engine-robot",
                                         "iam.gserviceaccount.com")),
    # No match because prefix isn't a serviceAccount
    test_case("user:kf-vmaster@"
              "container-engine-robot.iam.gserviceaccount.com",
              None),
  ]

  for c in cases:
    actual = cleanup_ci.parse_service_account_email(c.input)

    assert actual == c.expected


def test_trim_unused_bindings():
  this_dir = os.path.dirname(__file__)
  test_data_dir = os.path.join(this_dir, "test_data")
  with open(os.path.join(test_data_dir, "trim_bindings.input.yaml")) as hf:
    policy = yaml.load(hf)

  accounts = ["existsaccount@someproject.iam.gserviceaccount.com"]

  expected = set([
    "serviceAccount:existsaccount@someproject.iam.gserviceaccount.com",
    "serviceAccount:user2@nothisproject.iam.gserviceaccount.com",
    "serviceAccount:gcp@cloudbuild.gserviceaccount.com",
    "serviceAccount:kubeflow-releasing@kubeflow-releasing"
    ".iam.gserviceaccount.com"])

  project = "someproject"
  cleanup_ci.trim_unused_bindings(policy, accounts, project)

  actual_bindings = set(policy["bindings"][0]["members"])
  assert actual_bindings == expected

def test_parse_k8s_url_map():
  expected = cleanup_ci.K8S_URL_MAP_NAME("istio-system-envoy-ingress",
                                         "848f8392b2ce1c27")
  assert cleanup_ci._parse_k8s(
    "k8s-um-istio-system-envoy-ingress--848f8392b2ce1c27") == expected

if __name__ == "__main__":
  logging.basicConfig(
      level=logging.INFO,
      format=('%(levelname)s|%(asctime)s'
            '|%(pathname)s|%(lineno)d| %(message)s'),
    datefmt='%Y-%m-%dT%H:%M:%S',
    )
  logging.getLogger().setLevel(logging.INFO)
  pytest.main()
