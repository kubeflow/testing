from kubeflow.testing import cleanup_ci
import logging
import pytest

def test_match_endpoints():
  """Verify that cloud endpoint service names match the regex"""

  service_names = [
    "iap-ingress-kfctl-8c9b.endpoints.kubeflow-ci-deployment.cloud.goog",
  ]

  for s in service_names:
    assert cleanup_ci.is_match(s, patterns=cleanup_ci.MATCHING)

if __name__ == "__main__":
  logging.basicConfig(
      level=logging.INFO,
      format=('%(levelname)s|%(asctime)s'
            '|%(pathname)s|%(lineno)d| %(message)s'),
    datefmt='%Y-%m-%dT%H:%M:%S',
    )
  logging.getLogger().setLevel(logging.INFO)
  pytest.main()
