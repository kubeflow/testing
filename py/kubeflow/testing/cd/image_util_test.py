import collections
import logging
import pytest

from kubeflow.testing.cd import image_util # pylint: disable=no-name-in-module

def test_parse_image():
  test_case = collections.namedtuple("test_case", ("url", "expected"))

  cases = [
    test_case("gcr.io/repo/someimage",
              image_util.IMAGE_TUPLE("gcr.io/repo", "someimage", "", "")),
    test_case("gcr.io/repo/someimage:tag",
              image_util.IMAGE_TUPLE("gcr.io/repo", "someimage", "tag", "")),
    test_case("gcr.io/repo/someimage:tag@sha256:1234",
              image_util.IMAGE_TUPLE("gcr.io/repo", "someimage", "tag", "sha256:1234")),
    test_case("gcr.io/repo/someimage@sha256:1234",
              image_util.IMAGE_TUPLE("gcr.io/repo", "someimage", "", "sha256:1234")),
  ]

  for c in cases:
    actual = image_util.parse_image_url(c.url)

    assert actual == c.expected

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  # DO NOT SUBMIT
  test_parse_image()
  #pytest.main()
