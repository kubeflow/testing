# CLI tools to fetch Python library's license info

This doc aims to show how to get third party library license information for Kubeflow Python applications.

As a prerequisite, please read the [Go license tools guide](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/go-license-tools/README.md) on why third party library license compliance is important and how it is accomplished for Go applications. Specifically, this doc differs from the Go guide mainly on the way of getting dependencies using `pipenv` and source repository from PyPI.

## How to get all dependencies with license and source code?

### I. Setup
Download the Python files both in go-license-tools folder and this folder.

### II. Get all dependency repositories
1. Figure out all Python dependencies with `pipenv`. Your application doesn't have to use `pipenv` to manage its dependencies but we are using it here to find the transitive dependencies:

    - Install [pipenv](https://pypi.org/project/pipenv/).
    - Run `pipenv install ...` to install all your direct dependencies.
    - Run `pipenv lock` to generate lock file `Pipfile.lock` in JSON for all transitive dependencies.

2. Get GitHub source repositories for all the dependencies by running this script.
    ```
    python3 pipfile_to_github_repo.py
    ```
    This script parses the `Pipfile.lock` and looks up the source repositories registered on PyPI. You should see a file named `repo.txt` is generated and its content looks like this:
    ```
    AzureAD/azure-activedirectory-library-for-python
    tkem/cachetools
    certifi: None
    cffi: None
    ......
    ```
    Each line above is a GitHub repository name for a package. Unfortunately, not all packages have source repository information listed on PyPI. In this case, we use `<pakcage_name>: None` to denote such packages. In this example, `certifi` and `cffi` miss the source repository information and we have to manually search for source repositories and edit the information.

3. Manually edit source repository information. Once we find all the package source repositories, we need to update `repo.txt`. For example, we can replace
line `certifi: None` with its GitHub source repository `certifi/python-certifi`.

    However, we can't update `repo.txt` for `cffi` directly, because it is not hosted on GitHub but . We have to remember to update its license URI and type in the final `license_info.csv`, which is produced in the next step.

### III. Get all license URLs and types
This step is the same as [the one](https://github.com/kubeflow/testing/blob/master/py/kubeflow/testing/go-license-tools/README.md#iii-get-all-license-urls-and-types) described in the Go license tools guide, but you have to manually add the license information for code not hosted on GitHub.
