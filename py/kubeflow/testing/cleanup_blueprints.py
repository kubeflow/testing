"""Cleanup auto deployed blueprints.

Note: This is in a separate file from cleanup_ci because we wanted to start
using Fire and python3.

TODO(jlewi): The auto deployments reconciler (blueprint_reconciler) should have
its own logic to GC auto-deployments. Should this script not GC
auto-deployments? Should it focus on GC'ing test clusters that weren't
torn down when the test ended? Should we also cleanup any left overs
from blueprints? When I first wrote it it was only GC'ing auto-deployed
blueprints because that was all we had. We will probably need to change that
to support GC'ing left overs from tests that failed to do cleanup.
"""
import collections
import datetime
from dateutil import parser as date_parser
import fire
import logging

from kubeflow.testing import cnrm_clients
from kubeflow.testing import util
from kubernetes import client as k8s_client

# The names of various labels used to encode information about the
#
# Which branch the blueprint was deployed from
# TODO(jlewi): Where whould we define these so they are centrally located?
BRANCH_LABEL = "blueprint-branch"
NAME_LABEL = "kf-name"
AUTO_DEPLOY_LABEL = "auto-deploy"

def _iter_blueprints(namespace, context=None):
  """Return an iterator over blueprints.

  Args:
    namespace: The namespace to look for blueprints
    context: The kube context to use.
  """
  # We need to load the kube config so that we can have credentials to
  # talk to the APIServer.
  util.load_kube_config(persist_config=False, context=context)

  client = k8s_client.ApiClient()
  crd_api = cnrm_clients.CnrmClientApi(client, "containercluster")

  clusters = crd_api.list_namespaced(namespace)

  for c in clusters.get("items"):
    yield c

def _delete_blueprints(namespace, to_keep_names, context=None, dryrun=True):
  """Delete all auto-deployed resources that we don't want to keep.

  Args:
    namespace: The namespace that owns the CNRM objects.
    to_keep_names: Names of the blueprints to keep.
    context: The kubeconfig context to use


  This function deletes all auto-deployed resources that we don't want
  to keep. This function is intended to delete any orphaned resources.
  It works as follows.

    1. For each type of resource we issue a list to find all autodeployed
       resources
    2. We then remove any resource which belongs to a blueprint to keep
    3. We remove any resource that is less than 1 hours old
       * This is to avoid race conditions where a blueprint was created
         after to_keep was computedisks
    4. remaining resources are deleted.
  """

  util.load_kube_config(persist_config=False, context=context)

  client = k8s_client.ApiClient()
  crd_api = k8s_client.CustomObjectsApi(client)

  BASE_GROUP = "cnrm.cloud.google.com"
  CNRM_VERSION = "v1beta1"


  # List of resources to GC
  kinds = ["containercluster", "iampolicymember",
           "iamserviceaccount", "containernodepool",
           "computeaddress", "computedisk"]


  # Mappings from resource type to list of resources
  to_keep = collections.defaultdict(lambda: [])
  to_delete = collections.defaultdict(lambda: [])

  api_client = k8s_client.ApiClient()

  # Loop over resources and identify resources to delete.
  for kind in kinds:
    client = cnrm_clients.CnrmClientApi(api_client, kind)

    selector = "{0}=true".format(AUTO_DEPLOY_LABEL)
    results = client.list_namespaced(namespace, label_selector=selector)

    for i in results.get("items"):
      name = i["metadata"]["name"]

      if name in to_keep_names:
        to_keep[kind].append(name)
        continue

      creation = date_parser.parse(i["metadata"]["creationTimestamp"])
      age = datetime.datetime.now(creation.tzinfo) - creation
      if age < datetime.timedelta(hours=1):
        to_keep[kind].append(name)
        logging.info("Not GC'ing %s %s; it was created to recently", kind,
                     name)
        continue

      to_delete[kind].append(name)

  for kind in kinds:
    client = cnrm_clients.CnrmClientApi(api_client, kind)
    for name in to_delete[kind]:
      if dryrun:
        logging.info("Dryrun: %s %s would be deleted", kind, name)
      else:
        logging.info("Deleting: %s %s", kind, name)
        client.delete_namespaced(namespace, name, {})

  for kind in kinds:
    logging.info("Deleted %s:\n%s", kind, "\n".join(to_delete[kind]))
    logging.info("Kept %s:\n%s", kind, "\n".join(to_keep[kind]))

class Cleanup:
  @staticmethod
  def auto_blueprints(project, context, dryrun=True, blueprints=None): # pylint: disable=too-many-branches
    """Cleanup auto deployed blueprints.

    For auto blueprints we only want to keep the most recent N deployments.

    Args:
      project: The project that owns the deployments
      context: The kubernetes context to use to talk to the Cloud config
        Connector cluster.
      dryrun: (True) set to false to actually cleanup.
      blueprints: (Optional) iterator over CNRM ContainerCluster resources
       corresponding to blueprints.

    Returns:
      blueprints_to_delete: List of deployments to delete
      blueprints_to_keep: List of deployments to keep
    """
    logging.info("Cleanup auto blueprints")

    # Map from blueprint version e.g. "master" to a map of blueprint names to
    # their insert time e.g.
    # auto_deployments["master"]["kf-vbp-abcd"] returns the creation time
    # of blueprint "kf-vbp-abcd" which was created from the master branch
    # of the blueprints repo.
    auto_deployments = collections.defaultdict(lambda: {})

    if not blueprints:
      blueprints = _iter_blueprints(project, context=context)

    for b in blueprints:
      name = b["metadata"]["name"]
      if not b["metadata"].get("creationTimestamp", None):
        # This should not happen all K8s objects should have creation timestamp
        logging.error("Cluster %s doesn't have a deployment time "
                      "skipping it", b["metadata"]["name"])
        continue

      # Use labels to identify auto-deployed instances
      auto_deploy_label = b["metadata"].get("labels", {}).get(AUTO_DEPLOY_LABEL,
                                                              "false")

      is_auto_deploy = auto_deploy_label.lower() == "true"

      if not is_auto_deploy:
        logging.info("Skipping cluster %s; its missing the auto-deploy label",
                     name)

      # Tha name of blueprint
      kf_name = b["metadata"].get("labels", {}).get(NAME_LABEL, "")

      if not kf_name:
        logging.info("Skipping cluster %s; it is not an auto-deployed instance",
                     name)
        continue

      if kf_name != name:
        # TODO(jlewi): This shouldn't be happening. Hopefully this was just
        # temporary issue with the first couple of auto-deployed clusters I
        # created and we can delete this code.
        logging.error("Found cluster named:%s with label kf-name: %s. The name "
                      "will be used. This shouldn't happen. This hopefully "
                      "was just due to a temporary bug in the early versions "
                      "of create_kf_from_gcp_blueprint.py that should be fixed "
                      "so it shouldn't be happening in new instances anymore."
                      , name, kf_name)
        kf_name = name

      logging.info("Blueprint %s is auto deployed", kf_name)

      blueprint_branch = b["metadata"]["labels"].get(BRANCH_LABEL, "unknown")

      if blueprint_branch == "unknown":
        logging.warning("Blueprint %s was missing label %s", kf_name,
                        BRANCH_LABEL)

      if kf_name in auto_deployments[blueprint_branch]:
        continue

      auto_deployments[blueprint_branch][kf_name] = (
        date_parser.parse(b["metadata"]["creationTimestamp"]))

    # Garbage collect the blueprints
    to_keep = []
    to_delete = []
    for version, matched_deployments in auto_deployments.items():
      logging.info("For version=%s found deployments:\n%s", version,
                   "\n".join(matched_deployments.keys()))

      # Sort the deployment by the insert time
      pairs = matched_deployments.items()
      sorted_pairs = sorted(pairs, key=lambda x: x[1])

      # keep the 3 most recent deployments
      to_keep.extend([p[0] for p in sorted_pairs[-3:]])
      to_delete.extend([p[0] for p in sorted_pairs[:-3]])

    _delete_blueprints(project, to_keep, context=context,
                       dryrun=dryrun)

    logging.info("Finish cleanup auto blueprints")

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(Cleanup)
