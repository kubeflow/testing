# Build the docker image used to run the scripts
# to continuously update our docker files.
#
# The context for this docker file should be the root of the kubeflow/testing repository.
FROM ubuntu:18.04

RUN apt-get update -y && \
    apt-get install -y curl git python3.8 python3-pip wget && \
    ln -sf /usr/bin/python3.8 /usr/bin/python

RUN python3.8 -m pip install \
    fire \
    lint \
    watchdog

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

# Create go symlinks
RUN ln -sf /usr/local/go/bin/go /usr/local/bin && \
    ln -sf /usr/local/go/bin/gofmt /usr/local/bin && \
    ln -sf /usr/local/go/bin/godoc /usr/local/bin

RUN go get github.com/kelseyhightower/kube-rsa

COPY checkout.sh /usr/local/bin
COPY checkout_repos.sh /usr/local/bin
COPY setup_ssh.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/checkout* /usr/local/bin/setup_ssh.sh

COPY run_workflows.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/run_workflows.sh

COPY run_release.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/run_release.sh

# Install the hub CLI for git
RUN cd /tmp && \
    curl -LO  https://github.com/github/hub/releases/download/v2.11.2/hub-linux-amd64-2.11.2.tgz && \
    tar -xvf hub-linux-amd64-2.11.2.tgz && \
    mv hub-linux-amd64-2.11.2 /usr/local && \
    ln -sf /usr/local/hub-linux-amd64-2.11.2/bin/hub /usr/local/bin/hub

# Install kubectl
# We don't install via gcloud because we want 1.10 which is newer than what's in gcloud.
RUN  curl -LO https://storage.googleapis.com/kubernetes-release/release/v1.14.0/bin/linux/amd64/kubectl && \
    mv kubectl /usr/local/bin && \
    chmod a+x /usr/local/bin/kubectl

