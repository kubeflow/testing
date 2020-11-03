import os
import unittest
import mock
from kubeflow.testing import run_e2e_workflow
import six
import tempfile
import yaml

import pytest


class TestRunE2eWorkflow(unittest.TestCase):

  def assertItemsMatchRegex(self, expected, actual):
    """Check that expected matches actual.

    Args:
      Expected: List of strings. These can be regex.
      Actual: Actual items.
    """
    self.assertEqual(len(expected), len(actual))
    for index, e in enumerate(expected):
      # assertRegexpMatches uses re.search so we automatically append
      # ^ and $ so we match the beginning and end of the string.
      pattern = "^" + e + "$"
      six.assertRegex(self, actual[index], pattern)

if __name__ == "__main__":
  unittest.main()
