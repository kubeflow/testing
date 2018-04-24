import argparse
import fnmatch
import logging
import os
import subprocess

from kubeflow.testing import test_helper, util


def should_exclude(root, full_dir_excludes):
  for e in full_dir_excludes:
    if root.startswith(e):
      return True
  return False


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--src_dir",
    default=os.getcwd(),
    type=str,
    help=("The root directory of the source tree. Defaults to current "
          "directory."))
  args, _ = parser.parse_known_args()
  return args


def test_lint(test_case): # pylint: disable=redefined-outer-name
  logging.info('Running test_lint')
  args = parse_args()
  # Print out the pylint version because different versions can produce
  # different results.
  util.run(["pylint", "--version"])

  # kubeflow_testing is imported as a submodule so we should exclude it
  # TODO(jlewi): We should make this an argument.
  dir_excludes = [
    "dashboard/frontend/node_modules",
    "kubeflow_testing",
    "vendor",
  ]
  full_dir_excludes = [
    os.path.join(os.path.abspath(args.src_dir), f) for f in dir_excludes
  ]

  # TODO(jlewi): Use pathlib once we switch to python3.
  includes = ["*.py"]
  failed_files = []
  rc_file = os.path.join(args.src_dir, ".pylintrc")
  for root, dirs, files in os.walk(os.path.abspath(args.src_dir), topdown=True):
    # excludes can be done with fnmatch.filter and complementary set,
    # but it's more annoying to read.
    if should_exclude(root, full_dir_excludes):
      continue

    dirs[:] = [d for d in dirs]
    for pat in includes:
      for f in fnmatch.filter(files, pat):
        full_path = os.path.join(root, f)
        try:
          util.run(
            ["pylint", "--rcfile=" + rc_file, full_path], cwd=args.src_dir)
        except subprocess.CalledProcessError:
          failed_files.append(full_path[len(args.src_dir):])
  if failed_files:
    failed_files.sort()
    test_case.add_failure_info("Files with lint issues: {0}".format(
      ", ".join(failed_files)))
    logging.error("%s files had lint errors:\n%s", len(failed_files),
                  "\n".join(failed_files))
  else:
    logging.info("No lint issues.")


if __name__ == "__main__":
  test_case = test_helper.TestCase(name='test_lint', test_func=test_lint)
  test_suite = test_helper.init(name='py_lint', test_cases=[test_case])
  test_suite.run()
