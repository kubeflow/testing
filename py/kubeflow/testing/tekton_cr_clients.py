"""Some helper functions for working with Tekton resources."""
from kubernetes import client as k8s_client

# TODO(jlewi): Create a common base class to be shared with CnrmClients.
class TektonClientApi(k8s_client.CustomObjectsApi):
  """A wrapper around CustomObjectsApi."""

  def __init__(self, client, kind):
    """Create the client.

    Args:
      client: K8s client
      kind: The kind to generate the client for.
    """
    super(TektonClientApi, self).__init__(client)

    self.kind = kind
    self.version = "v1alpha1"

    self.group = "tekton.dev"

    if kind[-1] != "s":
      self.plural = kind.lower() + "s"
    else:
      self.plural = kind.lower() + "es"

  def list_namespaced(self, namespace, **kwargs):
    return self.list_namespaced_custom_object(
      self.group, self.version, namespace, self.plural, **kwargs)

  def delete_namespaced(self, namespace, name, body, **kwargs):
    return self.delete_namespaced_custom_object(self.group, self.version,
                                                namespace, self.plural, name,
                                                body, **kwargs)

  def create_namespaced(self, namespace, body, **kwargs):
    return self.create_namespaced_custom_object(self.group, self.version,
                                                namespace, self.plural, body,
                                                **kwargs)
