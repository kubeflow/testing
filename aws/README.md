<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Optional Test Infrastructure](#optional-test-infrastructure)
  - [Architecture](#architecture)
  - [Management](#management)
  - [Test LifeCycle](#test-lifecycle)
  - [Dashboards](#dashboards)
  - [Setting up a Kubeflow Repository to Use Optional-Test-Infra](#setting-up-a-kubeflow-repository-to-use-optional-test-infra)
  - [Writing an Argo Workflow for E2E Test](#writing-an-argo-workflow-for-e2e-test)
  - [Applying for Access to Optional-Test-Infra](#applying-for-access-to-optional-test-infra)
  - [Debugging failed E2E Test](#debugging-failed-e2e-test)
  - [Folder Organizations](#folder-organizations)
  - [Want to contribute](#want-to-contribute)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Optional Test Infrastructure

This documentation describes configuration and automation for Kubeflow Optional-Test-Infra.

## Architecture
The [architecture doc](https://github.com/kubeflow/testing/tree/master/aws/Doc/architecture.md) will give you a deep
understanding how optional-test-infra works and how different clusters interact with each other. 

## Management
Today we still rely on human to manipulate test-infra AWS resources, such as the number of EC2 instances.
We're now experimenting IaC(Infrastructure as Code) tool
[CDK](https://github.com/kubeflow/testing/tree/master/aws/IaC/CDK/test-infra/README.md)
to manage test-infra resources.

## Test LifeCycle
The [diagram](./Picture/TestLifeCycle.png) shows the phases that kubeflow tests goes through when you send a PR.

## Dashboards

* [Prow Dashboard](https://prow.kubeflow-testing.com/) shows what jobs are running or have recently run in prow
* [Argo Dashboard](https://argo.kubeflow-testing.com/) shows you what Argo workflow are running and logs
* [Tekton Dashboard](https://tekton.kubeflow-testing.com/) shows you what Tekton PipelineRuns are running and logs

## Setting up a Kubeflow Repository to Use Optional-Test-Infra

* [Adopting Optional-Test-Infra](https://github.com/kubeflow/testing/tree/master/aws/Doc/onboarding.md)
provides a detailed instruction for kubeflow application WG to onboard their kubeflow repo to use optional-test-infra.

## Writing an Argo Workflow for E2E Test
* [Writing Argo Workflow for E2E Tests](https://github.com/kubeflow/testing/tree/master/aws/Doc/argo_e2e.md)
* [TODO] PatrickXYS: need to provide more detailed instructions

## Applying for Access to Optional-Test-Infra
* [Access Control](https://github.com/kubeflow/testing/tree/master/aws/Access/README.md)

## Debugging failed E2E Test
[TODO] PatrickXYS: need detailed guidance

## Folder Organizations

Each sub-folder refer to different functionality for Optional-Test-Infra

* **User**: user-modifiable configuration files for all the clusters under Optional-Test-Infra concepts
* **GitOps**: ArgoCD sync changes in the folder to update cluster resources
* **Doc**: documentations for optional-test-infra
* **Picture**: pictures embedded in the documentations
* **testing**: testing artifacts storage
* **Access**: Infra Access Control for Kubeflow Community

## Want to contribute
Let's join us and start contributing! 

[TODO] PatrickXYS: Provide a detailed guidance for people who want to start contributing to optional-test-infra.  
[TODO] PatrickXYS: Provide a deep-dive doc for design of optional-test-infra.

