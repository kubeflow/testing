"""
This module contains misc utils used for Kubeflow testing
infrastructure. They include creating test cases/suites,
managing logs of test cases and initializing tests

This is intended to replace test_util.py
"""
import argparse
import logging
import os
import subprocess
import time
import xml.etree.ElementTree as ET
import junit_xml


class TestCase(junit_xml.TestCase):
  """A single test case."""

  def __init__(self, test_func, **kwargs):
    self.class_name = "Kubeflow"
    self.start_time = time.time()
    self.test_func = test_func
    self.failure_output = ''
    super(TestCase, self).__init__(**kwargs)

  def add_failure_info(self, output=None): # pylint: disable=arguments-differ
    """
    add_failure_info is used to add failure info to the test cases
    any message added to this will be logged in the test case failure
    output in gubernator
    """
    if output:
      if not self.failure_output:
        self.failure_output = ''
      self.failure_output += output + '\n'

class TestSuite(junit_xml.TestSuite):
  """A suite of test cases."""

  def __init__(self, name, test_dir, artifacts_dir, logs_dir, **kwargs):
    self.test_dir = test_dir
    self.artifacts_dir = artifacts_dir
    self.logs_dir = logs_dir
    super(TestSuite, self).__init__(name, **kwargs)

  def generate_xml(self):
    # Test grid has problems with underscores in the name.
    # https://github.com/kubeflow/kubeflow/issues/631
    # TestGrid currently uses the regex junit_(^_)*.xml so we only
    # want one underscore after junit.
    output_file = os.path.join(self.artifacts_dir,
                               "junit_" + self.name.replace("_", "-") + ".xml")
    # junit_xml produces a list of test suites, but gubernator
    # only parses a single test suite. So here we generate
    # the xml using junit-xml and only output the first test
    # suite in our output file
    xml_out = junit_xml.TestSuite.to_xml_string([self])
    first_test_suite = ET.fromstring(xml_out)[0]
    ET.ElementTree(first_test_suite).write(output_file)

  def run(self):
    """
    runs a test suite and makes logs available through the junit
    xml file
    """
    try:
      for test_case in self.test_cases:
        log_file_name = os.path.join(self.logs_dir, test_case.name + '.log')
        update_logging_handler(log_file_name)
        test_case.test_suite = self
        try:
          wrap_test(test_case)
        finally:
          if test_case.is_failure():
            logging.getLogger().handlers[-1].flush()
            with open(log_file_name, 'r') as test_log_file:
              test_case.add_failure_info(test_log_file.read())
    finally:
      self.generate_xml()


def wrap_test(test_case):
  """Wrap a test func.

  Test_func is a callable that contains the commands to perform a particular
  test.

  Args:
    test_case: A TestCase to be populated.

  Raises:
    Exceptions are reraised to indicate test failure.
  """
  try:
    test_case.test_func(test_case)
  except subprocess.CalledProcessError as e:
    logging.error("Subprocess failed;\n%s", e.output)
    test_case.add_failure_info("Subprocess failed;\n{0}".format(e.output))
    raise
  except Exception as e:
    logging.error("Test failed; %s", e.message)
    test_case.add_failure_info("Test failed; " + e.message)
    raise
  finally:
    test_case.elapsed_sec = time.time() - test_case.start_time


def update_logging_handler(file_name):
  """
  update_logging_handler updates the logging handler to
  log to file_name. We log to a separate file for every
  test case. This is so that we can read separate logs
  for each test case and show it in gubernator.
  """
  file_handler = logging.FileHandler(file_name)
  formatter = logging.Formatter(
    fmt=("%(levelname)s|%(asctime)s"
         "|%(filename)s:%(lineno)d| %(message)s"),
    datefmt="%Y-%m-%dT%H:%M:%S")
  file_handler.setFormatter(formatter)
  if len(logging.getLogger().handlers) == 1:
    logging.getLogger().addHandler(file_handler)
  else:
    logging.getLogger().handlers = [
      logging.getLogger().handlers[0], file_handler
    ]


def init(name, test_cases):
  """
  init initializes a Kubeflow test suite
  It defined the common flags, sets up logging and creates a TestSuite object
  """
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--test_dir",
    default=os.getcwd(),
    type=str,
    help="The test directory"
    "Defaults to current directory if not set.")

  parser.add_argument(
    "--artifacts_dir",
    default=os.path.join(os.getcwd(), "output", "artifacts"),
    type=str,
    help="Directory to use for artifacts that should be preserved after "
    "the test runs. Defaults to test_dir/output/artifacts if not set.")
  args, _ = parser.parse_known_args()

  if not os.path.exists(args.artifacts_dir):
    try:
      os.makedirs(args.artifacts_dir)
    # Ignore OSError because sometimes another process
    # running in parallel creates this directory at the same time
    except OSError:
      pass

  logging.basicConfig(
    level=logging.INFO,
    format=('%(levelname)s|%(asctime)s'
            '|%(filename)s:%(lineno)d| %(message)s'),
    datefmt='%Y-%m-%dT%H:%M:%S',
  )
  logging.getLogger().setLevel(logging.INFO)
  logs_dir = os.path.join(args.artifacts_dir, "logs")
  if not os.path.exists(logs_dir):
    try:
      os.makedirs(logs_dir)
    # Ignore OSError because sometimes another process
    # running in parallel creates this directory at the same time
    except OSError:
      pass
  return TestSuite(
    name=name,
    test_dir=args.test_dir,
    artifacts_dir=args.artifacts_dir,
    logs_dir=logs_dir,
    test_cases=test_cases)
