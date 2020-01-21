from kubeflow.testing import cleanup_ci
import collections
import logging
import pytest

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

if __name__ == "__main__":
  logging.basicConfig(
      level=logging.INFO,
      format=('%(levelname)s|%(asctime)s'
            '|%(pathname)s|%(lineno)d| %(message)s'),
    datefmt='%Y-%m-%dT%H:%M:%S',
    )
  logging.getLogger().setLevel(logging.INFO)
  pytest.main()
