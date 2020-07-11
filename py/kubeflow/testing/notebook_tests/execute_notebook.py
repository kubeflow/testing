import argparse
import datetime
import tempfile
import logging
import nbformat
import nbconvert
import os
import uuid
import papermill
from papermill import exceptions as papermill_exceptions

logger = logging.getLogger(__name__)

from google.cloud import storage
from kubeflow.testing import gcp_util
from kubeflow.testing import util

def execute_notebook(notebook_path, parameters=None):
  temp_dir = tempfile.mkdtemp()

  logging.info("Executing notebook")
  notebook_output_path = os.path.join(temp_dir, "out.ipynb")
  try:
    papermill.execute_notebook(notebook_path, notebook_output_path,
                               cwd=os.path.dirname(notebook_path),
                               parameters=parameters,
                               log_output=True)
  # Catch exceptions because we don't want to terminate because we still want
  # to upload output
  except papermill_exceptions.PapermillExecutionError as e:
    logging.error(f"Exception occurred while running notebook {notebook_path}")
    logging.error(f"Exception occurred while running notebook {e}")
  except Exception as e: # pylint: disable=broad-except
    logging.error(f"Unexpected exception occurred while running notebook "
                  f"{notebook_path}")
    logging.error(f"Unexpected exception occurred while running notebook {e}")
  logging.info(f"Finished executing notebook; saved to {notebook_output_path}")
  return notebook_output_path

def _upload_notebook_html(content, target):
  gcs_client = storage.Client()
  bucket_name, path = util.split_gcs_uri(target)

  bucket = gcs_client.get_bucket(bucket_name)

  logging.info("Uploading notebook to %s.", target)
  blob = bucket.blob(path)
  # Need to set content type so that if we browse in GCS we end up rendering
  # as html.
  blob.upload_from_string(content, content_type="text/html")

def run_notebook_test(notebook_path, parameters=None):
  # Ensure workload identity is ready.
  # TODO(jlewi): Need to skip this when not running on GCP.
  gcp_util.get_gcp_credentials()
  output_path = execute_notebook(notebook_path, parameters=parameters)

  logging.info(f"Reading notebook {output_path}")
  with open(output_path, "r") as hf:
    actual_output = hf.read()

  logging.info("Converting notebook to html")
  nb = nbformat.reads(actual_output, as_version=4)
  html_exporter = nbconvert.HTMLExporter()
  (html_output, _) = html_exporter.from_notebook_node(nb)
  gcs_path = os.getenv("OUTPUT_GCS")

  # Per https://github.com/kubeflow/testing/issues/715
  # we need to add some uniquness to the name since different test runs
  # will use the same OUTPUT_GCS directory
  subdir = datetime.datetime.now().strftime("%Y%m%d-%H%M")
  subdir = "-" + uuid.uuid4().hex[0:4]

  gcs_path = os.path.join(gcs_path, subdir, "notebook.html")

  logging.info(f"Uploading notebook to {gcs_path}")
  _upload_notebook_html(html_output, gcs_path)

class NotebookExecutor:
  @staticmethod
  def test(notebook_path):
    """Test a notebook.

    Args:
      notebook_path: Absolute path of the notebook.
    """
    run_notebook_test(notebook_path)

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(message)s|%(pathname)s|%(lineno)d|'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )

  # fire isn't available in the notebook image which is why we aren't
  # using it.
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--notebook_path", default="", type=str, help=("Path to the notebook"))

  args = parser.parse_args()

  NotebookExecutor.test(args.notebook_path)
