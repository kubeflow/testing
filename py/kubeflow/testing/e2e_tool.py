"""A helper, CLI tool for working with py_func's defining E2E tests.

This CLI provides methods for printing and submitting Argo workflows defined
by py_funcs.
"""
import fire
import logging
from kubernetes import client as k8s_client
import retrying
import yaml

from kubeflow.testing import run_e2e_workflow
from kubeflow.testing import util

class E2EToolMain(object): # pylint: disable=useless-object-inheritance
  """A helper class to add some convenient entry points."""
  def show(self, py_func, name=None, namespace=None): # pylint: disable=no-self-use
    """Print out the workflow spec.

    Args:
      py_func: Dotted name of the function defining the workflow
    """
    kwargs = {
      "name": name,
      "namespace": namespace,
    }
    workflow = run_e2e_workflow.py_func_import(py_func, kwargs)

    print(yaml.safe_dump(workflow))

  def apply(self, py_func, name=None, namespace=None, open_in_chrome=False): # pylint: disable=no-self-use
    """Create the workflow in the current cluster.

    Args:
      py_func: Dotted name of the function defining the workflow
    """
    kwargs = {
      "name": name,
      "namespace": namespace,
    }
    workflow = run_e2e_workflow.py_func_import(py_func, kwargs)

    util.load_kube_config(print_config=False)
    client = k8s_client.ApiClient()
    crd_api = k8s_client.CustomObjectsApi(client)

    group, version = workflow['apiVersion'].split('/')

    py_func_result = crd_api.create_namespaced_custom_object(
      group=group,
      version=version,
      namespace=namespace,
      plural='workflows',
      body=workflow)

    # Wait for a status to be returned and print out out
    @retrying.retry
    def get_wf_status():
      result = crd_api.get_namespaced_custom_object(
        group=group,
        version=version,
        namespace=namespace,
        plural='workflows',
        name=name)

      if not "status" in result:
        raise ValueError("Workflow object not ready yet.")
      return result

    result = get_wf_status()
    logging.info("Created workflow:\n%s", yaml.safe_dump(result))

    # TODO(jlewi): We are asumming the workflow is running in the Kubeflow CI
    # cluster. We should try to infer the correct endpoint by looking for an
    # appropriate ingress.
    ui_url = ("http://testing-argo.kubeflow.org/workflows/kubeflow-test-infra/{0}"
            "?tab=workflow".format(name))
    logging.info("URL for workflow: %s", ui_url)

    if open_in_chrome:
      util.run(["google-chrome", ui_url])

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(E2EToolMain)
