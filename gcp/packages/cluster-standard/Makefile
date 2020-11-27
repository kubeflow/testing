NAME?=NAME
PROJECT?=PROJECT
REPO_ROOT=../../../../
ACM_REPOS=$(REPO_ROOT)/acm-repos/kf-ci-management

set-values: FORCE
	kpt cfg set . name $(NAME)
	kpt cfg set . gcloud.core.project $(PROJECT)

FORCE: ;
