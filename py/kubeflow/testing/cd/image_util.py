"""Some utilities related to docker iamges."""

import collections
import os
import re

# A tuple for representing docker images
IMAGE_TUPLE = collections.namedtuple("image", ("registry",
                                               "name", "tag", "digest"))

def parse_image_url(url):
  """Parse a url representing a docker image

  Args:
    url: The url of an image;
    e.g. gcr.io/kubeflow-images-public:image@sha256:1234

  Returns:
    image_tuple: A tuple representing the parsed image
  """

  # Here are the different image formats
  # gcr.io/repo/someimage
  # gcr.io/repo/someimage:tag
  # gcr.io/repo/someimage:tag@sha256:digest
  # gcr.io/repo/someimage@sha256:digest

  # Split it into the name and tag.digest
  m = re.match("([^:@]*)([:@]?)(.*)", url)

  if not m:
    raise ValueError(f"Url {url} didn't match the expected pattern")

  registry_and_name = m.group(1)
  registry = os.path.dirname(registry_and_name)
  name = os.path.basename(registry_and_name)

  if not m.group(2):
    return IMAGE_TUPLE(registry, name, "", "")

  split = m.group(2)
  tag_and_digest = m.group(3)

  # only a digest
  if split == "@":
    return IMAGE_TUPLE(registry, name, "", tag_and_digest)

  if not "@" in tag_and_digest:
    # No digest
    return IMAGE_TUPLE(registry, name, tag_and_digest, "")

  tag, digest = tag_and_digest.split("@")

  return IMAGE_TUPLE(registry, name, tag, digest)
