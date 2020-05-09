# Build the docker image used to run the scripts
# to continuously update our docker files.
#
# The context for this docker file should be the root of the kubeflow/testing repository.
FROM ubuntu:18.04

RUN apt-get update -y && \
    apt-get install -y curl git python3.8 python3-pip wget && \
    ln -sf /usr/bin/python3.8 /usr/bin/python

# Install go
RUN cd /tmp && \
    wget -O /tmp/go.tar.gz https://redirector.gvt1.com/edgedl/go/go1.12.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go.tar.gz

# Install the hub CLI for git
RUN cd /tmp && \
    curl -LO  https://github.com/github/hub/releases/download/v2.13.0/hub-linux-amd64-2.13.0.tgz && \
    tar -xvf hub-linux-amd64-2.13.0.tgz && \
    mv hub-linux-amd64-2.13.0 /usr/local && \
    ln -sf /usr/local/hub-linux-amd64-2.13.0/bin/hub /usr/local/bin/hub

RUN export KUSTOMIZE_VERSION=3.2.0 && \
    cd /tmp && \
    curl -LO  https://github.com/kubernetes-sigs/kustomize/releases/download/v${KUSTOMIZE_VERSION}/kustomize_${KUSTOMIZE_VERSION}_linux_amd64 && \
    mv kustomize_${KUSTOMIZE_VERSION}_linux_amd64 /usr/local/bin/kustomize && \
    chmod a+x /usr/local/bin/kustomize


# Install gcloud
ENV PATH=${PATH}:/google-cloud-sdk/bin

RUN cd /tmp && \
    export GCLOUD_TAR=google-cloud-sdk-278.0.0-linux-x86_64.tar.gz && \
    curl -LO https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/${GCLOUD_TAR} && \
    tar xzf ${GCLOUD_TAR} -C / && \
    rm ${GCLOUD_TAR} && \
    /google-cloud-sdk/install.sh \
    --disable-installation-options \
    --bash-completion=false \
    --path-update=false \
    --usage-reporting=false && \
    gcloud components install alpha beta kubectl

COPY test-infra/auto-deploy/requirements.txt /tmp
RUN python -m pip install \
     -r /tmp/requirements.txt

# Create go symlinks
RUN ln -sf /usr/local/go/bin/go /usr/local/bin && \
    ln -sf /usr/local/go/bin/gofmt /usr/local/bin && \
    ln -sf /usr/local/go/bin/godoc /usr/local/bin

RUN mkdir -p /app

RUN cd /app && \
    mkdir -p /app/src/kubeflow

COPY py /app/src/kubeflow/testing/py
COPY test-infra/auto-deploy/templates /app/templates

ENV PYTHONPATH /app/src/kubeflow/testing/py:$PYTHONPATH

# See(https://github.com/tektoncd/pipeline/issues/1271): Tekton will put ssh
# credentials in /tekton/home. We can't change the home directory
# but we can create a symbolic link for .ssh
RUN mkdir -p /tekton/home && \
    ln -sf /tekton/home/.ssh /root/.ssh
