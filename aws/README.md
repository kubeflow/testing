<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Optional Test Infrastructure](#optional-test-infrastructure)
  - [Architecture](#architecture)
  - [Dashboards](#dashboards)
  - [Setting up a Kubeflow Repository to Use Optional-Test-Infra](#setting-up-a-kubeflow-repository-to-use-optional-test-infra)
  - [Writing an Argo Workflow for E2E Test](#writing-an-argo-workflow-for-e2e-test)
  - [Applying for Access to Optional-Test-Infra](#applying-for-access-to-optional-test-infra)
  - [Folder Organizations](#folder-organizations)
  - [Want to contribute](#want-to-contribute)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Optional Test Infrastructure

This documentation describes configuration and automation for Kubeflow Optional-Test-Infra.

## Architecture
The [architecture doc](https://github.com/kubeflow/testing/tree/master/aws/Doc/architecture.md) will give you a deep
understanding how optional-test-infra works and how different clusters interact with each other. 

## Dashboards

* [Prow Dashboard](https://prow.kubeflow-testing.com/) shows what jobs are running or have recently run in prow
* [Argo Dashboard](https://argo.kubeflow-testing.com/) shows you what Argo workflow are running and logs
* [Tekton Dashboard](https://tekton.kubeflow-testing.com/) shows you what Tekton PipelineRuns are running and logs

## Setting up a Kubeflow Repository to Use Optional-Test-Infra

* [Adopting Optional-Test-Infra](https://github.com/kubeflow/testing/tree/master/aws/Doc/onboarding.md)
provides a detailed instruction for kubeflow WG to onboard their kubeflow repo to use optional-test-infra.

## Writing an Argo Workflow for E2E Test
* [Writing Argo Workflow for E2E Tests](https://github.com/kubeflow/testing/tree/master/aws/Doc/argo_e2e.md)
* [TODO] PatrickXYS: need to provide more detailed instructions

## Applying for Access to Optional-Test-Infra
* The [Access Granting](https://docs.google.com/document/d/1hrjIDO7UQ8l5uvADSxbiyM2GDfst1L7vyIKekrrdlwA/edit#heading=h.dix8w86ghq2) 
doc provides detailed instructions to apply Editor/Viewer Permissions to Optional-Test-infra DataPlane.
* [TODO] PatrickXYS: develop [IAM as Code](https://github.com/kubeflow/testing/issues/848) to GitOps permission granting in open-source community 

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

