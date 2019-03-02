# Docker image for nightly deployment cronjob.
#
FROM gcr.io/kubeflow-ci/test-worker:v20190302-c0829e8-dirty-f1d98c
MAINTAINER Gabriel Wen

# Purpose of auto_deploy.sh is to have a script as kickstarter. This script is used to pull fresh copy from
# Github and run with them.
COPY checkout_lib /usr/local/bin/py/checkout_lib
COPY lib-args.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/lib-args.sh
COPY auto_deploy.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/auto_deploy.sh
