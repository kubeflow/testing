#!/usr/bin/python
"""A script to copy kubernetes secrets from one namespace to another
"""

import fire
from google.cloud import storage
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client import rest
import logging
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

    client = k8s_client.ApiClient()
    api = k8s_client.CoreV1Api(client)

    try:
      source_secret = api.read_namespaced_secret(src_name, src_namespace)
    except rest.ApiException as e:
      if e.status != 404:
        raise

    if not source_secret:
      raise ValueError(f"Secret {source} doesn't exist")

    # delete metadata fields
    for f in ["creation_timestamp", "owner_references", "resource_version",
              "self_link", "uid"]:
      setattr(source_secret.metadata, f, None)

    source_secret.metadata.name = dest_name
    source_secret.metadata.namespace = dest_namespace

    api.create_namespaced_secret(dest_namespace, source_secret)
    logging.info(f"Created secret {dest}")

if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(message)s|%(pathname)s|%(lineno)d|'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )

  fire.Fire(SecretCreator)
