# Docker image for running E2E tests using Argo.

FROM ubuntu:xenial
MAINTAINER Jeremy Lewi

# Never prompt the user for choices on installation/configuration of packages
ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=linux
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV KUSTOMIZE_VERSION 2.0.3

# gcc & python-dev are needed so we can install crcmod for gsutil
# also includes installations for Python3
RUN set -ex \
    && apt-get update -yqq \
    && apt-get install -yqq --no-install-recommends \
    build-essential \
    cmake \
    curl \
    locales \
    uuid-runtime \
    wget \
    ca-certificates \
    ca-certificates-java \
    git \
    emacs \
    jq \
    zip \
    unzip \
    gcc \
    openjdk-8-jdk \
    ssh \
    mercurial \
    python-dev \
    python-setuptools \
    python-pip \
    python3-dev \
    python3-setuptools \
    python3-pip \
    && python -V \
    && python3 -V \
    && update-ca-certificates -f \
    && apt-get clean \
    && rm -rf \
    /var/lib/apt/lists/* \
    /tmp/* \
    /var/tmp/* \
    /usr/share/man \
    /usr/share/doc \
    /usr/share/doc-base

# Install go
RUN cd /tmp && \
    wget -O /tmp/go.tar.gz https://redirector.gvt1.com/edgedl/go/go1.12.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go.tar.gz

# Install gcloud
ENV PATH=/root/go/bin:/usr/local/go/bin:/google-cloud-sdk/bin:/workspace:${PATH} \
    CLOUDSDK_CORE_DISABLE_PROMPTS=1

RUN go get github.com/kelseyhightower/kube-rsa

RUN wget -q https://dl.google.com/dl/cloudsdk/channels/rapid/google-cloud-sdk.tar.gz && \
    tar xzf google-cloud-sdk.tar.gz -C / && \
    rm google-cloud-sdk.tar.gz && \
    /google-cloud-sdk/install.sh \
    --disable-installation-options \
    --bash-completion=false \
    --path-update=false \
    --usage-reporting=false && \
    gcloud components install alpha beta

# Install Helm
RUN wget -O /tmp/get_helm.sh \
    https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get && \
    chmod 700 /tmp/get_helm.sh && \
    /tmp/get_helm.sh && \
    rm /tmp/get_helm.sh

# Initialize helm
RUN helm init --client-only

# Install  Node.js
RUN curl -sL https://deb.nodesource.com/setup_8.x | bash - \
    && apt-get install -y nodejs

# Install yarn
RUN curl -sS http://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add - \
    && echo "deb http://dl.yarnpkg.com/debian/ stable main" | tee /etc/apt/sources.list.d/yarn.list \
    && apt-get update -yqq \
    && apt-get install -yqq --no-install-recommends yarn


# Install glide
RUN cd /tmp && \
    wget -O glide-v0.13.0-linux-amd64.tar.gz \
    https://github.com/Masterminds/glide/releases/download/v0.13.0/glide-v0.13.0-linux-amd64.tar.gz && \
    tar -xvf glide-v0.13.0-linux-amd64.tar.gz && \
    mv ./linux-amd64/glide /usr/local/bin/

# Install ksonnet. We install multiple versions of ks to support different versions
# of ksonnet applications. Newer versions of ksonnet are backwards compatible but
# that can require upgrading the app which isn't something we want to be forced to.
# (see https://github.com/kubeflow/testing/issues/220).
RUN cd /tmp && \
    wget -O ks.tar.gz \
    https://github.com/ksonnet/ksonnet/releases/download/v0.11.0/ks_0.11.0_linux_amd64.tar.gz && \
    tar -xvf ks.tar.gz && \
    mv ks_0.11.0_linux_amd64/ks /usr/local/bin && \
    chmod a+x /usr/local/bin/ks

RUN cd /tmp && \
    wget -O ks-12.tar.gz \
    https://github.com/ksonnet/ksonnet/releases/download/v0.12.0/ks_0.12.0_linux_amd64.tar.gz && \
    tar -xvf ks-12.tar.gz && \
    mv ks_0.12.0_linux_amd64/ks /usr/local/bin/ks-12 && \
    chmod a+x /usr/local/bin/ks-12

RUN cd /tmp && \
    wget -O ks-13.tar.gz \
    https://github.com/ksonnet/ksonnet/releases/download/v0.13.1/ks_0.13.1_linux_amd64.tar.gz && \
    tar -xvf ks-13.tar.gz && \
    mv ks_0.13.1_linux_amd64/ks /usr/local/bin/ks-13 && \
    chmod a+x /usr/local/bin/ks-13

RUN wget -O /usr/local/bin/kustomize \
    https://github.com/kubernetes-sigs/kustomize/releases/download/v${KUSTOMIZE_VERSION}/kustomize_${KUSTOMIZE_VERSION}_linux_amd64 && \
    chmod a+x /usr/local/bin/kustomize

RUN cd /tmp && \
    wget https://github.com/google/jsonnet/archive/v0.11.2.tar.gz && \
    tar -xvf v0.11.2.tar.gz && \
    cd jsonnet-0.11.2 && \
    make && \
    mv jsonnet /usr/local/bin && \
    rm -rf /tmp/v0.11.2.tar.gz && \
    rm -rf /tmp/jsonnet-0.11.2

COPY ./Pipfile ./Pipfile.lock /tmp/

# Install various python libraries for both Python 2 and 3 (for now)
# Don't upgrade pip for now because it seems to be broken
# https://github.com/pypa/pip/issues/5240
RUN cd /tmp/ && \
    pip2 install -U wheel filelock && \
    pip2 install pipenv && \
    pip2 install requests && \
    pip2 install prometheus_client fire && \
    pipenv install --system --two && \
    pip3 install -U wheel filelock gitpython fire

RUN pip3 install pipenv==2018.10.9
RUN cd /tmp/ && pipenv install --system --three

# Force update of googleapipython client
# Do this after pipenv because we want to override what pipenv installs.
RUN pip2 install --upgrade google-api-python-client==1.7.0

# Install the hub CLI for git
RUN cd /tmp && \
    curl -LO  https://github.com/github/hub/releases/download/v2.11.2/hub-linux-amd64-2.11.2.tgz && \
    tar -xvf hub-linux-amd64-2.11.2.tgz && \
    mv hub-linux-amd64-2.11.2 /usr/local && \
    ln -sf /usr/local/hub-linux-amd64-2.11.2/bin/hub /usr/local/bin/hub

RUN pip install yq

COPY checkout.sh /usr/local/bin
COPY checkout_repos.sh /usr/local/bin
COPY setup_ssh.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/checkout* /usr/local/bin/setup_ssh.sh

COPY run_workflows.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/run_workflows.sh

COPY run_release.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/run_release.sh

# Install docker.
RUN curl  https://get.docker.com/ | sh

# Install kubectl
# We don't install via gcloud because we want 1.10 which is newer than what's in gcloud.
RUN  curl -LO https://storage.googleapis.com/kubernetes-release/release/v1.10.0/bin/linux/amd64/kubectl && \
    mv kubectl /usr/local/bin && \
    chmod a+x /usr/local/bin/kubectl

# Work around for https://github.com/ksonnet/ksonnet/issues/298
ENV USER root

# Install Bazel
RUN cd /tmp && \
    wget -O /tmp/bazel-installer.sh https://github.com/bazelbuild/bazel/releases/download/0.24.1/bazel-0.24.1-installer-linux-x86_64.sh && \
    chmod +x bazel-installer.sh && \
    ./bazel-installer.sh --user

ENV PATH=root/bin:${PATH}

ENV JAVA_HOME /usr/lib/jvm/java-8-openjdk-amd64/
RUN export JAVA_HOME

# Add the directory where we will checkout kubeflow/testing
# which contains shared scripts.
ENV PYTHONPATH /src/kubeflow/testing/py

ENTRYPOINT ["/usr/local/bin/run_workflows.sh"]
