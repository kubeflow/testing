# CLI tools to fetch go library's license info

## Why we need this?

When we release go library images (can be considered as redistributing third
party binary).

We need to do the following to be compliant:
* Put license declarations in the image for licenses of all dependencies and transitive dependencies.
* Mirror source code in the image for code with MPL, EPL, GPL or CDDL licenses.

It's not an easy task to get license of all (transitive) dependencies of a go
library. Thus, we need these tools to automate this task.

## How to get all dependencies with license and source code?

### I. Setup
Download this folder to your local folder namely `<license_tool>` and install it:
```
$ python <license_tool>/setup.py install
```

### II. Get all dependency repositories
1. Collect dependencies and transitive dependencies in a Go library into a text file called `dep.txt`, where each line is a valid golang import module name. For example
    ```
    ......
    cloud.google.com/go
    github.com/BurntSushi/toml
    github.com/beorn7/perks
    github.com/bmatcuk/doublestar
    ......
    ```

    Typical ways to get it:
    * `gopkg` for package management. `gopkg` has a [Gopkg.lock file](https://github.com/argoproj/argo/blob/master/Gopkg.lock)
    with all of its dependencies and transitive dependencies. All the name fields in this file is what we need. You can run `parse-toml-dep.py` to parse it.
    * [Official go modules](https://blog.golang.org/using-go-modules) has a [go.mod file](https://github.com/minio/minio/blob/master/go.mod) describing its direct dependencies. Run command

        ```$ go list -m all | cut -d ' ' -f 1 > dep.txt```

        to get final versions that will be used in a build for all direct and indirect dependencies, ([reference](https://github.com/golang/go/wiki/Modules#daily-workflow)).

    **Reminder:** don't forget to put your library itself into `dep.txt`.
2. Run `$ python <licence_tool>/get_github_repo.py` to resolve github repositories of golang imports. Not all imports can be figured out by my script, needs manual help for <2% of libraries. For example, you may see an output like this:
    ```
    ......
    Successfully resolved github repo for 89 dependencies and saved to repo.txt. Failed to resolve 3 dependencies.
    We failed to resolve the following dependencies:
    gomodules.xyz/jsonpatch/v2
    honnef.co/go/tools
    ml_metadata
    ```

    For a library we cannot resolve, manually put it in `dep_repo.manual.csv`, so the tool knows how to find its github repo in the future. For example, the corresponding `dep_repo.manual.csv` for the example above is
    ```
    gomodules.xyz/jsonpatch/v2,gomodules/jsonpatch
    honnef.co/go/tools,dominikh/go-tools
    ml_metadata,google/ml-metadata
    ```
 3. Rerun the command in this to resolve all repositories this time:
    ```
    $ python <license_tool>/get_github_repo.py

    ......
    Successfully resolved github repo for 92 dependencies and saved to repo.txt. Failed to resolve 0 dependencies.
    ```

### III. Get all license URLs and types

1.  Crawl github license info of these libraries via the following command to produce the `license_info.csv` file. (Not all repositories have github recognizable license, needs manual help for <2% of libraries)
    ```
    $ python <license_tool>/third_party/cli/get_github_license_info.py --github-api-token-file=<github_token_file>
    ......
    Fetching license for google/ml-metadata
    Fetching license for kubernetes-sigs/controller-runtime
    Fetching license for kubernetes-sigs/testing_frameworks
    Fetching license for kubernetes-sigs/yaml
    Fetched github license info, 91 succeeded, 0 failed.
    ```
    You have to create a `<github_token_file>` in order to access GitHub repositories, because it sends a lot of requests to github. Follow instructions in `get-github-license-info -h`.

    For repositories that fails to fetch license, it's usually because their github repo
    doesn't have a github understandable license file. Check its readme and
    update correct info into `license-info.csv`. (Usually, use its README file which mentions license.)

2. Fill in missing license information. If you open `license_info.csv`, you can see some fields are marked as `Other`. We have to update them to the right license types. First we need to grep all these unknown license URLs:
    ```
    $ cat license_info.csv | grep Other | cut -d ',' -f 2

    GoogleCloudPlatform/gcloud-golang,https://github.com/googleapis/google-cloud-go/blob/master/LICENSE,Other,https://raw.githubusercontent.com/googleapis/google-cloud-go/master/LICENSE
    ghodss/yaml,https://github.com/ghodss/yaml/blob/master/LICENSE,Other,https://raw.githubusercontent.com/ghodss/yaml/master/LICENSE
    gogo/protobuf,https://github.com/gogo/protobuf/blob/master/LICENSE,Other,https://raw.githubusercontent.com/gogo/protobuf/master/LICENSE
    ......
    ```

    Now we can open these license all at once in Chrome via a plugin called [OpenList](https://chrome.google.com/webstore/detail/openlist/nkpjembldfckmdchbdiclhfedcngbgnl?hl=en).

    After checking the license content one by one, we can now create `additional_license_info.csv` to record the right license types. The content  of `additional_license_info.csv` looks like this:
    ```
    https://github.com/googleapis/google-cloud-go/blob/master/LICENSE,Apache License 2.0
    https://github.com/ghodss/yaml/blob/master/LICENSE,MIT
    https://github.com/gogo/protobuf/blob/master/LICENSE,BSD 3-Clause "New" or "Revised" License
    ......
    ```

    Finally, we can patch the additional license types in `additional_license_info.csv` on `license_info.csv` to get the final list of licenses with types.

    ```
    $  python patch_additional_license_info.py
    ```


3. Run `concatenate-license` to crawl full text license files for all dependencies and concat them into one file.

    Defaults to read license info from `license-info.csv`. Writes to `license.txt`.
    Put `license.txt` to `third_party/library/license.txt` where it is read when building docker images.
4. Manually update a list of dependencies that requires source code, put it into `third_party/library/repo-MPL.txt`.

## Add CI tests for license information.
It is considered as best practice to continuously test whether the right licence information is presented in the `license.txt` file for every new commit in your code repository. So that it is always safe to deliver a new image from the source code.

For examples, you can add the following tests into your CI pipeline.

1. Check if `dep.txt` is updated and force the license information to be updated in the same PR.

    Suppose your repository uses standard Go module and `dep.txt` is checked in. The test Shell script can simply be
    ```
    go list -m all | cut -d ' ' -f 1 > /tmp/generated_dep.txt

    if ! diff /tmp/generated_dep.txt dep.txt; then
        echo "Please update the license file for changed dependencies."
        exit 1
    fi
    ```

2. Check if the final `license.txt` is up-to-date. The test Shell script can be
    ```
    python3 concatenate_license.py --output=/tmp/generated_license.txt

    if ! diff /tmp/generated_license.txt license.txt; then
        echo "Please regenerate third_party/license.txt."
        exit 1
    fi
    ```
