import collections
from dateutil import parser as date_parser
import re

STORAGE_SUFFIX = "-storage"

# The label to keep track of the git commit for the label manifests
MANIFESTS_COMMIT_LABEL = "git-manifests"
BRANCH_LABEL = "git-manifests-branch"
# Label for the auto deployment config
AUTO_NAME_LABEL = "auto-name"

def is_storage_deployment(name):
  return name.endswith(STORAGE_SUFFIX)

class AutoDeploymentName:
  """A class representing the name of an auto deployed KF instance."""

  _PATTERN = re.compile("kf-(.*)-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{3}")
  def __init__(self, name="", version=""):
    # Name for the kf instance
    self.name = name
    # The version tag e.g. master
    self.version = version

  @classmethod
  def from_deployment_name(cls, name):
    """Construct the name from the name of a deployment manager name.

    Args:
      name: The name of a deployment manager name; can be a storage name
       or the deployment manager config for the cluster.

    Returns:
      The name or None if its not a valid name
    """
    if name.endswith(STORAGE_SUFFIX):
      name = name[:-len(STORAGE_SUFFIX)]

    m = cls._PATTERN.match(name)

    if not m:
      return None

    result = AutoDeploymentName()
    result.name = name
    result.version = m.group(1)

    return result

  def __eq__(self, other):
    if self.name != other.name:
      return False
    if self.version != other.version:
      return False

    return True

class AutoDeployment:
  """A class describing an auto deployment."""

  def __init__(self, manifests_branch=None, create_time=None,
               deployment_name=None, labels=None):
    # The kubeflow/manifests branch it was deployed from
    self.manifests_branch = manifests_branch
    # The time it was created
    if isinstance(create_time, (str)):
      create_time = date_parser.parse(create_time)
    self.create_time = create_time

    # The name of the GCP deployment
    self.deployment_name = deployment_name
    self.labels = labels

    if not self.labels:
      self.labels = {}

  def __repr__(self):
    return (f"AutoDeployment(deployment_name=\"{self.deployment_name}\", "
            f"manifests_branch=\"{self.manifests_branch}\", "
            f"create_time=\"{self.create_time}\")")

  def __eq__(self, other):
    for f in ["manifests_branch", "create_time", "deployment_name"]:
      if getattr(self, f) != getattr(other, f):
        return False

    return True


AUTO_DEPLOYMENT_NAME = collections.namedtuple("auto_deploy_name",
                                              ("name", "version"))
