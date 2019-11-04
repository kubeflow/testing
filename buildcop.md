# Build Cop Playbook

The build cop is responsible for keeping the testing and releasing infrastructure green
so that developers can remain productive.

This doc captures processes to follow to achieve that goal.

Also see [playbook.md](playbook.md) for dealing with various issues
with the test and release infrastructure.


[Build Cop Kanban Board](https://github.com/orgs/kubeflow/projects/35) - Use this
Kanban board to track ongoing issues

[Engprod Kanban board](https://github.com/orgs/kubeflow/projects/13) - Use this for medium to long term
  work to improve the release and test infrastructure

## Monitoring the test grid

* **Pro Tip** In test grid use Group By Hierarchy Pattern with pattern `[\w-]+` to group tests by workflow

  * Links below should include the pattern as a query argument


* Check all the dashboards listed below

  * If there are any failing tests check if there is already an issue in the [Build Cop Kanban Board](https://github.com/orgs/kubeflow/projects/35?add_cards_query=is%3Aopen) and if not file one


* Periodic Kanban boards for master

  * [kubeflow-periodic-master](https://k8s-testgrid.appspot.com/sig-big-data#kubeflow-periodic-master&group-by-hierarchy-pattern=%5B%5Cw-%5D%2B)

  * [kubeflow-periodic-kfctl](https://k8s-testgrid.appspot.com/sig-big-data#kubeflow-periodic-kfctl&group-by-hierarchy-pattern=%5B%5Cw-%5D%2B)

  * [kubeflow-manifests-periodic-master](https://k8s-testgrid.appspot.com/sig-big-data#kubeflow-manifests-periodic-master&group-by-hierarchy-pattern=%5B%5Cw-%5D%2B)

  * [kubeflow-periodic-examples](https://k8s-testgrid.appspot.com/sig-big-data#kubeflow-periodic-examples&group-by-hierarchy-pattern=%5B%5Cw-%5D%2B)

* Periodic Kanban boards for releases
   
  * [kubeflow-periodic-0-7](https://k8s-testgrid.appspot.com/sig-big-data#kubeflow-periodic-0-7&group-by-hierarchy-pattern=%5B%5Cw-%5D%2B)

     * See [kubeflow/testing#498](https://github.com/kubeflow/testing/issues/498) there is ongoing work
       to get this setup.

  * The following kanban boards aren't setup yet but should be monitored once they are

    * kubeflow-kfctl-periodic-0-7
    * kubeflow-manifests-periodic-0-7
    * kubeflow-examples-periodic-0-7
 
## Presubmit Breakages

* Presubmit breakages should be treated as P0

* If a PR breaks the presubmits the process should be to **roll it back first** and not to try to forward fix it.