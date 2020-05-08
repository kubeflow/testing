"""Some helper functions for working with CNRM resources."""
from kubernetes import client as k8s_client

class CnrmClientApi(k8s_client.CustomObjectsApi):
  """A wrapper around CustomObjectsApi."""

  def __init__(self, client, kind):
    """Create the client.

    Args:
      client: K8s client
      kind: The kind to generate the client for.
    """
    super(CnrmClientApi, self).__init__(client)

    self.kind = kind
    self.version = "v1beta1"

    if kind in ["containercluster", "containernodepool"]:
      self.group = "container.cnrm.cloud.google.com"
    elif kind in ["iampolicymember", "iamserviceaccount"]:
      self.group = "iam.cnrm.cloud.google.com"
    elif kind in ["computeaddress", "computedisk"]:
      self.group = "compute.cnrm.cloud.google.com"
    else:
      raise ValueError("No CNRM client configured for kind {0}".format(kind))

    if kind[-1] != "s":
      self.plural = kind + "s"
    else:
      self.plural = kind + "es"

  def list_namespaced(self, namespace, **kwargs):
    return self.list_namespaced_custom_object(
      self.group, self.version, namespace, self.plural, **kwargs)

  def delete_namespaced(self, namespace, name, body, **kwargs):
    return self.delete_namespaced_custom_object(self.group, self.version,
                                                namespace, self.plural, name,
                                                body, **kwargs)

  # TODO(jlewi): Add other methods as needed.
