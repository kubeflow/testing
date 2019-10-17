import os
import pytest

def pytest_addoption(parser):
  parser.addoption(
      "--src_dir",
      action="store",
      default=os.getcwd(),
      help=("The root directory of the source tree. Defaults to current "
            "directory."))

  parser.addoption(
      "--rcfile",
      default="",
      action="store",
      help=("Path to the rcfile."))

@pytest.fixture
def rcfile(request):
  return request.config.getoption("--rcfile")

@pytest.fixture
def src_dir(request):
  return request.config.getoption("--src_dir")
