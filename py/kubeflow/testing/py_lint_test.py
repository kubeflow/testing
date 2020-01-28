import fnmatch
import logging
import os
import subprocess

from kubeflow.testing import util

import pytest

logging.basicConfig(
    level=logging.INFO,
    format=('%(levelname)s|%(asctime)s'
            '|%(pathname)s|%(lineno)d| %(message)s'),
    datefmt='%Y-%m-%dT%H:%M:%S',
)
logging.getLogger().setLevel(logging.INFO)

def should_exclude(root, full_dir_excludes):
  for e in full_dir_excludes:
    if root.startswith(e):
      return True
  return False


def test_lint(record_xml_attribute, src_dir, rcfile): # pylint: disable=redefined-outer-name
  # Override the classname attribute in the junit file.
  # This makes it easy to group related tests in test grid.
  # http://doc.pytest.org/en/latest/usage.html#record-xml-attribute
  util.set_pytest_junit(record_xml_attribute, "test_py_lint")
  logging.info('Running test_lint')

  pylint_bin = "pylint"

  # Print out the pylint version because different versions can produce
  # different results.
  util.run([pylint_bin, "--version"])

  # kubeflow_testing is imported as a submodule so we should exclude it
  # TODO(jlewi): We should make this an argument.
  dir_excludes = [
    "dashboard/frontend/node_modules",
    "kubeflow_testing",
    "dev-kubeflow-org/ks-app/vendor",
    # TODO(https://github.com/kubeflow/testing/issues/560) stop skipping
    # py/kubeflow/testing/cd once we update python & pylint so f style
    # strings don't generate lint errors.
    "kubeflow/testing",
    "release-infra",
  ]
  full_dir_excludes = [
    os.path.join(os.path.abspath(src_dir), f) for f in dir_excludes
  ]

  logging.info("Directories to be excluded: %s", ",".join(full_dir_excludes))

  # TODO(jlewi): Use pathlib once we switch to python3.
  includes = ["*.py"]
  failed_files = []
  if not rcfile:
    rcfile = os.path.join(src_dir, ".pylintrc")

  for root, dirs, files in os.walk(os.path.abspath(src_dir), topdown=True):
    # Exclude vendor directories and all sub files.
    if "vendor" in root.split(os.sep):
      continue

    # excludes can be done with fnmatch.filter and complementary set,
    # but it's more annoying to read.
    if should_exclude(root, full_dir_excludes):
      logging.info("Skipping directory %s", root)
      continue

    dirs[:] = [d for d in dirs]
    for pat in includes:
      for f in fnmatch.filter(files, pat):
        full_path = os.path.join(root, f)
        try:
          util.run(
            [pylint_bin, "--rcfile=" + rcfile, full_path], cwd=src_dir)
        except subprocess.CalledProcessError:
          failed_files.append(full_path[len(src_dir):])
  if failed_files:
    failed_files.sort()
    logging.error("%s files had lint errors:\n%s", len(failed_files),
                  "\n".join(failed_files))
  else:
    logging.info("No lint issues.")

  assert not failed_files

if __name__ == "__main__":
  logging.basicConfig(
      level=logging.INFO,
      format=('%(levelname)s|%(asctime)s'
              '|%(pathname)s|%(lineno)d| %(message)s'),
      datefmt='%Y-%m-%dT%H:%M:%S',
  )
  logging.getLogger().setLevel(logging.INFO)
  pytest.main()
