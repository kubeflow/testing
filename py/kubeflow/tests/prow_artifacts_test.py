import json
import os
import unittest
import mock
from kubeflow.testing import prow_artifacts
from google.cloud import storage  # pylint: disable=no-name-in-module

class TestProw(unittest.TestCase):
  @mock.patch("kubeflow.testing.prow_artifacts.time.time")
  def testCreateStartedPresubmit(self, mock_time):  # pylint: disable=no-self-use
    """Test create started for presubmit job."""
    mock_time.return_value = 1000

    os.environ["REPO_OWNER"] = "fake_org"
    os.environ["REPO_NAME"] = "fake_name"
    os.environ["PULL_PULL_SHA"] = "123abc"
    expected = {
        "timestamp": 1000,
        "repos": {
            "fake_org/fake_name": "123abc",
        },
        "metadata": {
          "workflow1-ui": "http://argo",
        },
    }

    ui_urls = {
      "workflow1": "http://argo",
    }
    actual = prow_artifacts.create_started(ui_urls)

    self.assertEqual(expected, json.loads(actual))

  @mock.patch("kubeflow.testing.prow_artifacts.time.time")
  def testCreateFinished(self, mock_time):  # pylint: disable=no-self-use
    """Test create finished job."""
    os.environ["REPO_OWNER"] = "fake_org"
    os.environ["REPO_NAME"] = "fake_name"
    os.environ["PULL_REFS"] = "master:abcd,72:efgh"
    mock_time.return_value = 1000
    workflow_phase = {
      "wfA": "Succeeded"
    }
    test_urls = {
      "wfA": "https://example.com",
    }
    expected = {
        "timestamp": 1000,
        "result": "FAILED",
        "metadata": {
          "repos": {
            "fake_org/fake_name": "master:abcd,72:efgh"
            },
          "wfA-phase": "Succeeded",
          "wfA-ui": "https://example.com",
        },
    }

    actual = prow_artifacts.create_finished(False, workflow_phase, test_urls)
    os.environ.pop("PULL_REFS")
    self.assertEqual(expected, json.loads(actual))

  @mock.patch("kubeflow.testing.prow_artifacts.util.run")
  def testCopyArtifactsPresubmit(self, mock_run):  # pylint: disable=no-self-use
    """Test copy artifacts to GCS."""

    os.environ = {}
    os.environ["REPO_OWNER"] = "fake_org"
    os.environ["REPO_NAME"] = "fake_name"
    os.environ["PULL_NUMBER"] = "72"
    os.environ["BUILD_NUMBER"] = "100"
    os.environ["PULL_PULL_SHA"] = "123abc"
    os.environ["JOB_NAME"] = "kubeflow-presubmit"
    os.environ["JOB_TYPE"] = "presubmit"

    args = ["--artifacts_dir=/tmp/some/dir", "copy_artifacts",
            "--bucket=some_bucket"]
    prow_artifacts.main(args)

    mock_run.assert_called_once_with(
      ["gsutil", "-m", "rsync", "-r", "/tmp/some/dir",
       "gs://some_bucket/pr-logs/pull/fake_org_fake_name/72/kubeflow-presubmit"
       "/100"],
    )

  def testCreateSymlink(self): # pylint: disable=no-self-use
    gcs_client = mock.MagicMock(spec=storage.Client)
    mock_bucket = mock.MagicMock(spec=storage.Bucket)
    gcs_client.get_bucket.return_value = mock_bucket
    mock_blob = mock.MagicMock(spec=storage.Blob)
    mock_bucket.blob.return_value = mock_blob
    # We can't add the decorator the instance method because that would
    # interfere with creating gcs_client since storage.Client would then
    # point to the mock and not the actual class.
    with mock.patch("kubeflow.testing.prow_artifacts.storage"
                    ".Client") as mock_client:
      mock_client.return_value = gcs_client

      os.environ["REPO_OWNER"] = "fake_org"
      os.environ["REPO_NAME"] = "fake_name"
      os.environ["PULL_NUMBER"] = "72"
      os.environ["BUILD_NUMBER"] = "100"
      os.environ["PULL_PULL_SHA"] = "123abc"
      os.environ["JOB_NAME"] = "kubeflow-presubmit"
      os.environ["JOB_TYPE"] = "presubmit"

      args = ["--artifacts_dir=/tmp/some/dir", "create_pr_symlink",
              "--bucket=some-bucket"]
      prow_artifacts.main(args)

      mock_blob.upload_from_string.assert_called_once_with(
        "gs://some-bucket/pr-logs/pull/fake_org_fake_name/72"
        "/kubeflow-presubmit/100")

if __name__ == "__main__":
  unittest.main()
