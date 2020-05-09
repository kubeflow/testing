import collections
from dateutil import parser as date_parser

STORAGE_SUFFIX = "-storage"

# The label to keep track of the git commit for the label manifests
MANIFESTS_COMMIT_LABEL = "git-manifests"
BRANCH_LABEL = "git-manifests-branch"
# Label for the auto deployment config
AUTO_NAME_LABEL = "auto-version-name"

def is_storage_deployment(name):
  return name.endswith(STORAGE_SUFFIX)

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

    self.location = ""
    self.zone = ""

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

  def to_dict(self):
    d = {}

    for a in ["manifests_branch", "deployment_name", "labels", "zone"]:
      d[a] = getattr(self, a)

    d["create_time"] = self.create_time.isoformat()
    return d

AUTO_DEPLOYMENT_NAME = collections.namedtuple("auto_deploy_name",
                                              ("name", "version"))
