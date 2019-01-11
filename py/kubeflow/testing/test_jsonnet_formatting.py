"""
test_jsonnet_formatting verfies that all jsonnet
files in args.src_dir are formatted
"""
import argparse
import filecmp
import fnmatch
import itertools
import logging
import os
import tempfile

from kubeflow.testing import test_helper, util


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--src_dir",
    default=os.getcwd(),
    type=str,
    help=("The root directory of the source tree. Defaults to current "
          "directory."))
  parser.add_argument(
    "--exclude_dirs",
    default="",
    type=str,
    help="Comma separated directories which should be excluded from the test")
  args, _ = parser.parse_known_args()
  return args


def is_formatted(file_name):
  outfile = tempfile.NamedTemporaryFile(delete=False).name
  util.run([
    "jsonnet", "fmt", file_name, "--output-file", outfile, "--string-style",
    "d", "--comment-style", "s", "--indent", "2"
  ])
  try:
    return filecmp.cmp(file_name, outfile)
  finally:
    os.remove(outfile)

def is_excluded(file_name, exclude_dirs):
  for exclude_dir in exclude_dirs:
    if file_name.startswith(exclude_dir):
      return True
  return False

def test_jsonnet_formatting(test_case): # pylint: disable=redefined-outer-name
  logging.info('Running test_jsonnet_formatting')
  args = parse_args()
  exclude_dirs = []
  if args.exclude_dirs:
    exclude_dirs = args.exclude_dirs.split(',')
  for dirpath, _, filenames in os.walk(args.src_dir):
    jsonnet_files = fnmatch.filter(filenames, '*.jsonnet')
    libsonnet_files = fnmatch.filter(filenames, '*.libsonnet')
    for file_name in itertools.chain(jsonnet_files, libsonnet_files):
      full_path = os.path.join(dirpath, file_name)
      if not is_excluded(full_path, exclude_dirs) and not is_formatted(full_path):
        test_case.add_failure_info("ERROR : {0} is not formatted".format(full_path))


if __name__ == "__main__":
  test_case = test_helper.TestCase(
    name='test_jsonnet_formatting', test_func=test_jsonnet_formatting)
  test_suite = test_helper.init(
    name='test_jsonnet_formatting', test_cases=[test_case])
  test_suite.run()
