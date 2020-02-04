import collections
import logging
import pytest

from kubeflow.testing.auto_deploy import util

def test_auto_deployment_name():
  test_case = collections.namedtuple("test_case", ("name", "expected"))

  test_cases = [
    test_case("kf-vmaster-0126-823",
              util.AutoDeploymentName("kf-vmaster-0126-823", "vmaster")),
    test_case("kf-vmaster-0126-abc",
              util.AutoDeploymentName("kf-vmaster-0126-abc", "vmaster")),
    test_case("kf-vmaster-0126-abc-storage",
              util.AutoDeploymentName("kf-vmaster-0126-abc", "vmaster")),
    test_case("kf-v1-0-0126-abc",
              util.AutoDeploymentName("kf-v1-0-0126-abc", "v1-0")),
    test_case("kf-v1-0-0126-abc-storage",
              util.AutoDeploymentName("kf-v1-0-0126-abc", "v1-0")),
    test_case("kf-invalidname", None),
  ]

  for c in test_cases:
    actual = util.AutoDeploymentName.from_deployment_name(c.name)

    if c.expected is None:
      assert actual is None
    else:
      assert actual == c.expected, "Failed for name={0}".format(c.name)

if __name__ == "__main__":
  logging.basicConfig(
      level=logging.INFO,
      format=('%(levelname)s|%(asctime)s'
            '|%(pathname)s|%(lineno)d| %(message)s'),
    datefmt='%Y-%m-%dT%H:%M:%S',
    )
  logging.getLogger().setLevel(logging.INFO)
  pytest.main()
