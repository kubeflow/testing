"""YAML utilities
"""
import requests
import urllib
import yaml

def load_file(path):
  """Load a YAML file.

  Args:
    path: Path to the YAML file; can be a local path or http URL

  Returs:
    data: The parsed YAML.
  """
  url_for_spec = urllib.parse.urlparse(path)

  if url_for_spec.scheme in ["http", "https"]:
    data = requests.get(path)
    return yaml.load(data.content)
  else:
    with open(path, 'r') as f:
      config_spec = yaml.load(f)
      return config_spec
