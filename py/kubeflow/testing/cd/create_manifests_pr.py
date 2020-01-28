"""A Python script to open a PR updating the manifests repo."""

import fire
import logging
import os
import re
import subprocess
import tempfile

from kubeflow.testing import util
from kubeflow.testing.cd import image_util

KUBEfLOW_BOT_EMAIL = "ci-bot-owners@kubeflow.org"
KUBEFLOW_BOT_NAME = "kubeflow-bot"
class PRCreator:

  @staticmethod
  def apply(image_url, src_image_url,
            manifests_dir, manifests_base, default_email=KUBEfLOW_BOT_EMAIL,
            default_name=KUBEFLOW_BOT_NAME):
    """Create a PR.

    Args:
      image_url: The URL to update the image to
      src_image_url: The URL of the image to be set.
      manifests_dir: Path to the directory containing the kustomization.yaml
        file to be updated
      manifests_base: The name of the branch to use as the base of the PR
    """
    logging.info(f"Creating a PR")
    logging.info(f"image_url={image_url}")
    logging.info(f"src_image_url={src_image_url}")
    logging.info(f"manifests_dir={manifests_dir}")
    logging.info(f"manifests_base={manifests_base}")

    image = image_util.parse_image_url(image_url)


    # The name of the branch needs to be in sync with the expected name
    # used in update_kf_apps.py because we use the branch name to look
    # for an existing PR
    new_branch_name = f"update_{image.name}_{image.tag}"

    # Tekton will automatically mount the ssh private key and known hosts stored in the git secret
    # in /tekton/home/.ssh
    # however since this scriptt runs in our test worker image  it ends up using /root/.sssh
    # See https://github.com/tektoncd/pipeline/issues/1271:
    # Tekton will mount the .ssh config in /tekton/home.ssh

    # TODO(jlewi): Do we need to do the ssh stuff?
    # Maybe we should move that into its Tekton step if necessary?
    # Along with the git config steps.
    #ln -sf /tekton/home/.ssh /root/.ssh
    #ssh-keyscan -t rsa github.com > /root/.ssh/known_hosts
    #cd /workspace/manifests

    # Do a full fetch to unshallow the clone
    # it looks like Tekton might do a shallow checkout
    manifests_repo = util.run(["git", "rev-parse", "--show-toplevel"],
                              cwd=manifests_dir)

    # GitHub user to store the fork
    email = None
    user_name = None
    try:
      email = util.run(["git", "config", "--get", "user.email"])
      user_name  = util.run(["git", "config", "--get", "user.name"])
    except subprocess.CalledProcessError as e:
      # git config --get returns non zero exit code if it isn't set
      logging.warning(f"Getting git email failed: output:\n {e.output}\n."
                      f"This usually means user.email isn't set.")

    if not email:
      logging.info(f"git config user.email not set; defaulting to "
                   f"{default_email}")
      email = default_email
      user_name = default_name
      util.run(["git", "config", "--global", "user.email",
                email])
      util.run(["git", "config", "--global", "user.name",
                user_name])

    try:
      util.run(["git", "fetch", "--unshallow"], cwd=manifests_repo)
    except subprocess.CalledProcessError as e:
      # Ignore errors if the repository already isn't shallow.
      if not re.match(".*unshallow on a complete repository.*", e.output):
        raise
    # Create a new branch for the pull request
    try:
      util.run(["git", "checkout", "-b", new_branch_name,
                f"origin/{manifests_base}"], cwd=manifests_repo)
    except subprocess.CalledProcessError as e:
      # The branch might already exist if we are running locally and rerunning
      if re.match(".*branch.*already.*exists.*", e.output):
        logging.warning(f"Branch {new_branch_name} already exists")
        util.run(["git", "checkout", new_branch_name], cwd=manifests_repo)
      else:
        raise
    # Add the kubeflow-bot repo
    try:
      util.run(["git", "remote", "add", user_name,
                f"git@github.com:{user_name}/manifests.git"],
               cwd=manifests_repo)
    except subprocess.CalledProcessError as e:
      # Ignore errors if the repository already isn't shallow.
      if not re.match(".*remote.*already.*exists.*", e.output):
        raise

    util.run(["kustomize", "edit", "set", "image",
              f"{src_image_url}={image_url}"],
             cwd=manifests_dir)

    # Regenerate the tests
    tests_dir = os.path.join(manifests_repo, "tests")
    util.run(["make", "generate-changed-only"], tests_dir)

    # TODO(jlewi): Move this into its own step in the tekton workflow
    # git config --global user.email "ci-bot-owners@kubeflow.org"
    # git config --global user.name "kubeflow-bot"

    image_commit = image.tag.split("-", 1)[-1]

    # We currently prefix the commit with a g so we need to strip it.
    if image_commit[0] == "g":
      image_commit = image_commit[1:]

    with tempfile.NamedTemporaryFile(prefix=f"tmpAutoUpdatePr_{image.name}",
                                     delete=False, mode="w") as hf:
      hf.write(f"[auto PR] Update the {image.name} image to tag {image.tag}\n")
      hf.write("\n")

      # TODO(jlewi): Could we provide a link to the commit at which the image
      # was built? How would we know which source repo it came from? that
      # would likely need to be provided as extra information.
      hf.write(f"* image {image_url}\n")

      # TODO(jlewi): We shouldn't hardcode the repository name. We can parse kubeflow_repo_url
      # This will be easier to do once we rewrite this in python.
      hf.write(f"* Image built from kubeflow/kubeflow@{image_commit}\n")

      message_file = hf.name

    try:
      util.run(["git", "commit", "-a", "-F", message_file], cwd=manifests_repo)
    except subprocess.CalledProcessError as e:
      if re.search(".*nothing to commit.*", e.output):
        logging.warning("Nothing to commit. This likely indicates changes "
                        "were already commited in a previous run")
      else:
        raise

    util.run(["git", "push", user_name, new_branch_name, "-f"],
             cwd=manifests_repo)

    try:
      util.run(["hub", "pull-request", "-f", "-b", f"kubeflow:{manifests_base}",
                "-F", message_file], cwd=manifests_repo)
    except subprocess.CalledProcessError as e:
      if re.search(".*already exists.*", e.output):
        logging.warning("Nothing to commit. This likely indicates the PR was "
                        "created in a previous run")
      else:
        raise

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(PRCreator)

