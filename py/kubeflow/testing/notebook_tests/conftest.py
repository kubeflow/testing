import pytest

def pytest_addoption(parser):
  parser.addoption(
    "--name", help="Name for the job. If not specified one was created "
    "automatically", type=str, default="")
  parser.addoption(
    "--namespace", help=("The namespace to run in. This should correspond to"
                         "a namespace associated with a Kubeflow namespace."),
                   type=str,
    default="default-profile")
  parser.addoption(
    "--image_file", help="Yaml file containing the docker image to use. Can be "
                         "GCS path",
    type=str,
    default="")
  parser.addoption(
    "--notebook_path", help=("Path to the testing notebook file"),
    type=str, default="")
  parser.addoption(
    "--test-target-name", help=("Test target name, used as junit class name."),
    type=str, default="notebook-test")
  parser.addoption(
    "--artifacts-gcs", help=("GCS to upload artifacts to. This location "
                             "should be writable from the cluster running "
                             "the notebook."),
    type=str, default="")

@pytest.fixture
def name(request):
  return request.config.getoption("--name")

@pytest.fixture
def namespace(request):
  return request.config.getoption("--namespace")

@pytest.fixture
def image_file(request):
  return request.config.getoption("--image_file")

@pytest.fixture
def notebook_path(request):
  return request.config.getoption("--notebook_path")

@pytest.fixture
def test_target_name(request):
  return request.config.getoption("--test-target-name")

@pytest.fixture
def artifacts_gcs(request):
  return request.config.getoption("--artifacts-gcs")
