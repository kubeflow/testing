import os
import unittest
import mock
from kubeflow.testing import run_e2e_workflow
import six
import tempfile
import yaml


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

  @mock.patch("kubeflow.testing.run_e2e_workflow.prow_artifacts"
              ".finalize_prow_job")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util"
              ".maybe_activate_service_account")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util.upload_file_to_gcs")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util.upload_to_gcs")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util.load_kube_config")
  @mock.patch("kubeflow.testing.run_e2e_workflow.argo_client.wait_for_workflows")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util.configure_kubectl")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util.run")
  def testMainPresubmit(self, mock_run, mock_configure, *unused_mocks):  # pylint: disable=no-self-use,unused-argument
    """Test create started for presubmit job."""

    os.environ = {}
    os.environ["REPO_OWNER"] = "fake_org"
    os.environ["REPO_NAME"] = "fake_name"
    os.environ["PULL_NUMBER"] = "77"
    os.environ["PULL_PULL_SHA"] = "123abc"
    os.environ["JOB_NAME"] = "kubeflow-presubmit"
    os.environ["JOB_TYPE"] = "presubmit"
    os.environ["BUILD_NUMBER"] = "1234"
    os.environ["BUILD_ID"] = "11"

    args = ["--project=some-project", "--cluster=some-cluster",
            "--zone=us-east1-d", "--bucket=some-bucket",
            "--app_dir=/some/dir",
            "--component=workflows"]
    run_e2e_workflow.main(args)

    mock_configure.assert_called_once_with("some-project", "us-east1-d",
                                           "some-cluster",)

    expected_calls = [
      ["ks", "version"],
      ["ks", "env", "add", "kubeflow-presubmit-legacy-77-123abc-1234-.*"],
      ["ks", "param", "set", "--env=.*", "workflows", "name",
           "kubeflow-presubmit-legacy-77-123abc-1234-[0-9a-z]{4}"],
      ["ks", "param", "set",
           "--env=.*",
           "workflows", "prow_env",
           "BUILD_ID=11,BUILD_NUMBER=1234,JOB_NAME=kubeflow-presubmit,"
           "JOB_TYPE=presubmit,PULL_NUMBER=77,PULL_PULL_SHA=123abc,"
           "REPO_NAME=fake_name,REPO_OWNER=fake_org"],
      ["ks", "param", "set",
           "--env=.*",
           "workflows", "namespace",
           "kubeflow-test-infra"],
      ["ks", "param", "set",
           "--env=.*",
           "workflows", "bucket", "some-bucket"],
      ["ks", "show", "kubeflow-presubmit.*", "-c", "workflows"],
      ["ks", "apply", "kubeflow-presubmit.*", "-c", "workflows"],
    ]

    for i, expected in enumerate(expected_calls):
      self.assertItemsMatchRegex(
        expected,
        mock_run.call_args_list[i][0][0])
      if i > 0:
        self.assertEqual(
           "/some/dir",
           mock_run.call_args_list[i][1]["cwd"])

  @mock.patch("kubeflow.testing.run_e2e_workflow.prow_artifacts"
              ".finalize_prow_job")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util"
              ".maybe_activate_service_account")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util.upload_file_to_gcs")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util.upload_to_gcs")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util.load_kube_config")
  @mock.patch("kubeflow.testing.run_e2e_workflow.argo_client.wait_for_workflows")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util.configure_kubectl")
  @mock.patch("kubeflow.testing.run_e2e_workflow.util.run")
  def testWithConfig(self, mock_run, mock_configure, *unused_mocks):  # pylint: disable=no-self-use,unused-argument
    """Test creating a workflow from a config file."""

    config = {
      "workflows": [
        {"app_dir": "kubeflow/testing/workflows",
         "component": "workflows",
         "name": "wf",
         "params": {
           "param1": "valuea",
           "param2": 10,
         },
        },]
    }
    with tempfile.NamedTemporaryFile(delete=False) as hf:
      yaml.dump(config, hf)
      name = hf.name
    os.environ = {}
    os.environ["REPO_OWNER"] = "fake_org"
    os.environ["REPO_NAME"] = "fake_name"
    os.environ["PULL_NUMBER"] = "77"
    os.environ["PULL_PULL_SHA"] = "123abc"
    os.environ["JOB_NAME"] = "kubeflow-presubmit"
    os.environ["JOB_TYPE"] = "presubmit"
    os.environ["BUILD_NUMBER"] = "1234"
    os.environ["BUILD_ID"] = "11"

    args = ["--project=some-project", "--cluster=some-cluster",
            "--zone=us-east1-d", "--bucket=some-bucket",
            "--config_file=" + name,
            "--repos_dir=/src"]
    run_e2e_workflow.main(args)

    mock_configure.assert_called_once_with("some-project", "us-east1-d",
                                           "some-cluster",)

    expected_calls = [
      ["ks", "version"],
      ["ks", "env", "add", "kubeflow-presubmit-wf-77-123abc-1234-.*"],
      ["ks", "param", "set", "--env=.*", "workflows", "name",
           "kubeflow-presubmit-wf-77-123abc-1234-[0-9a-z]{4}"],
      ["ks", "param", "set",
           "--env=.*",
           "workflows", "prow_env",
           "BUILD_ID=11,BUILD_NUMBER=1234,JOB_NAME=kubeflow-presubmit,"
           "JOB_TYPE=presubmit,PULL_NUMBER=77,PULL_PULL_SHA=123abc,"
           "REPO_NAME=fake_name,REPO_OWNER=fake_org"],
      ["ks", "param", "set",
           "--env=.*",
           "workflows", "namespace",
           "kubeflow-test-infra"],
      ["ks", "param", "set",
           "--env=.*",
           "workflows", "bucket", "some-bucket"],
      ["ks", "param", "set",
           "--env=.*",
           "workflows", "param1", "valuea"],
      ["ks", "param", "set",
           "--env=.*",
           "workflows", "param2", "10"],
      ["ks", "show", "kubeflow-presubmit.*", "-c", "workflows"],
      ["ks", "apply", "kubeflow-presubmit.*", "-c", "workflows"],
    ]

    for i, expected in enumerate(expected_calls):
      self.assertItemsMatchRegex(
        expected,
        mock_run.call_args_list[i][0][0])
      if i > 0:
        self.assertEqual(
           "/src/kubeflow/testing/workflows",
           mock_run.call_args_list[i][1]["cwd"])

if __name__ == "__main__":
  unittest.main()
