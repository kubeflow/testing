
import logging
import pytest

from kubeflow.testing import gcp_util

def test_location():
  assert gcp_util.location_to_type("us-central1-f") == gcp_util.ZONE_LOCATION
  assert gcp_util.location_to_type("us-central1") == gcp_util.REGION_LOCATION

if __name__ == "__main__":
  logging.basicConfig(
      level=logging.INFO,
      format=('%(levelname)s|%(asctime)s'
            '|%(pathname)s|%(lineno)d| %(message)s'),
    datefmt='%Y-%m-%dT%H:%M:%S',
    )
  logging.getLogger().setLevel(logging.INFO)

  pytest.main()

