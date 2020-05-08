"""A simple CLI to create Kubernetes contexts."""
import logging
import fire
import subprocess
import re

class ContextCreator:
  @staticmethod
  def create(project, location, cluster, name, namespace):
    """Create a context for the given GCP cluster.

    Args:
      project: Project that owns the cluster
      location: zone or region for the cluster
      cluster: Name of the cluster
      name: Name to give the context
      namespace: Namespace to use for the context.
    """

    if re.match("[^-]+-[^-]+-[^-]", location):
      location_type = "zone"
    else:
      location_type = "region"
    subprocess.check_call(["gcloud", f"--project={project}", "container",
                           "clusters", "get-credentials",
                           f"--{location_type}={location}", cluster])

    current_context = subprocess.check_output(["kubectl", "config",
                                               "current-context"]).strip()
    subprocess.check_call(["kubectl", "config", "rename-context",
                           current_context,  name])

    # Set the namespace
    subprocess.check_call(["kubectl", "config", "set-context", "--current",
                           "--namespace={namespace}"])

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(ContextCreator)
