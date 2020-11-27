NAME?=NAME
PROJECT?=PROJECT
REPO_ROOT=../../../../
ACM_REPOS=$(REPO_ROOT)/acm-repos/kf-ci-management

set-values: FORCE
	kpt cfg set -R . name $(NAME)
	kpt cfg set -R . gcloud.core.project $(PROJECT)

FORCE: ;
