import argparse
import fnmatch
import logging
import os
import subprocess

from kubeflow.testing import test_helper, util


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


def py_test(test_case):  # pylint: disable=redefined-outer-name
  logging.info('Running py_test')
  args = parse_args()

  # kubeflow_testing is imported as a submodule so we should exclude it
  # TODO(jlewi): Perhaps we should get a list of submodules and exclude
  # them automatically?
  dir_excludes = ["vendor"]
  includes = ["*_test.py"]
  failed_files = []

  num_failed = 0
  for root, dirs, files in os.walk(args.src_dir, topdown=True):
    # excludes can be done with fnmatch.filter and complementary set,
    # but it's more annoying to read.
    dirs[:] = [d for d in dirs if d not in dir_excludes]
    for pat in includes:
      for f in fnmatch.filter(files, pat):
        full_path = os.path.join(root, f)
        try:
          util.run(["python", full_path], cwd=args.src_dir)
        except subprocess.CalledProcessError:
          failed_files.append(full_path[len(args.src_dir):])
          num_failed += 1
  if num_failed:
    logging.error("%s tests failed.", num_failed)
    test_case.add_failure_info("{0} tests failed: {1}.".format(
      num_failed, ", ".join(failed_files)))
  else:
    logging.info("No test issues.")


if __name__ == "__main__":
  test_case = test_helper.TestCase(name='py_test', test_func=py_test)
  test_suite = test_helper.init(name='py_checks', test_cases=[test_case])
  test_suite.run()
