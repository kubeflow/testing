#!/usr/bin/python
"""A script to copy kubernetes secrets from one namespace to another
"""

import base64
import fire
from google.cloud import storage
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client import rest
import logging
import yaml
import os
import re
import subprocess

GCS_REGEX = re.compile("gs://([^/]*)(/.*)?")

def split_gcs_uri(gcs_uri):
  """Split a GCS URI into bucket and path."""
  m = GCS_REGEX.match(gcs_uri)
  bucket = m.group(1)
  path = ""
  if m.group(2):
    path = m.group(2).lstrip("/")
  return bucket, path


def _read_gcs_path(gcs_path):
  bucket_name, blob_name = split_gcs_uri(gcs_path)

  storage_client = storage.Client()

  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(blob_name)
  contents = blob.download_as_string().decode()

  return contents

class SecretCreator:

  def __init__(self):
    k8s_config.load_kube_config(persist_config=False)

    self._k8s_client = k8s_client.ApiClient()



  @staticmethod
  def from_gcs(secret_name, gcs_path):
    """Create a secret from a GCS.

    Args:
      secret_name: {namespace}.{secret_name} of the secret to create
      gcs_path: The path of the GCS file to create the secret from.
    """
    bucket_name, blob_name = split_gcs_uri(gcs_path)

    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    contents = blob.download_as_string().decode()

    file_name = os.path.basename(blob_name)
    namespace, name = secret_name.split("/", 1)
    subprocess.check_call(["kubectl", "-n", namespace, "create",
                           "secret", "generic",
                           name,
                           f"--from-literal=f{file_name}={contents}"])

  def copy_secret(self, source, dest):
    """Create a secret from one namespace to another.

    Args:
      source: {namespace}.{secret name}
      dest: {namespace}.{secret name}
    """
    src_namespace, src_name = source.split(".", 1)
    dest_namespace, dest_name = dest.split(".", 1)

    api = k8s_client.CoreV1Api(client)

    try:
      return api.read_namespaced_secret(name, namespace)
    except rest.ApiException as e:
      if e.status != 404:
        raise

    source_secret = get_secret(src_namespace, src_name, self._k8s_client)

    if not source_secret:
      raise ValueError(f"Secret {source} doesn't exist")

    # delete metadata fields
    for f in ["creation_timestamp", "owner_references", "resource_version",
              "self_link", "uid"]:
      del source_secret["metadata"][f]

    source_secret["metadata"]["name"] = dest_name
    source_secret["metadata"]["namespace"] = dest_namespace


    data = subprocess.check_output(["kubectl", "-n", src_namespace, "get",
                                    "secrets", src_name, "-o",
                                    "yaml"])

    encoded = yaml.load(data)
    decoded = {}

    for k, v in encoded["data"].items():
      decoded[k] = base64.b64decode(v).decode()

    command = ["kubectl", "create", "-n", dest_namespace, "secret",
               "generic", dest_name]

    for k, v in decoded.items():
      command.append(f"--from-literal={k}={v}")

    subprocess.check_call(command)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(message)s|%(pathname)s|%(lineno)d|'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )

  fire.Fire(SecretCreator)

