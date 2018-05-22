# Docker image for running E2E tests using Argo.

FROM ubuntu:xenial
MAINTAINER Jeremy Lewi

# Never prompt the user for choices on installation/configuration of packages
ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=linux
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# gcc & python-dev are needed so we can install crcmod for gsutil
# also includes installations for Python3
RUN set -ex \
    && apt-get update -yqq \
    && apt-get install -yqq --no-install-recommends \
    build-essential \
    curl \
    locales \
    wget \
    ca-certificates \
    git \
    zip \
    unzip \
    gcc \
    ssh \
    python-dev \
    python-setuptools \
    python-pip \
    python3-dev \
    python3-setuptools \
    python3-pip \
    && python -V \
    && python3 -V \
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
    wget -O /tmp/go.tar.gz https://redirector.gvt1.com/edgedl/go/go1.9.2.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go.tar.gz

# Install gcloud
ENV PATH=/usr/local/go/bin:/google-cloud-sdk/bin:/workspace:${PATH} \
    CLOUDSDK_CORE_DISABLE_PROMPTS=1

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

# Install ksonnet
RUN cd /tmp && \
    wget -O ks.tar.gz \
    https://github.com/ksonnet/ksonnet/releases/download/v0.10.2/ks_0.10.2_linux_amd64.tar.gz && \
    tar -xvf ks.tar.gz && \
    mv ks_0.10.2_linux_amd64/ks /usr/local/bin && \
    chmod a+x /usr/local/bin/ks

RUN cd /tmp && \
    wget https://github.com/google/jsonnet/archive/v0.9.5.tar.gz && \
    tar -xvf v0.9.5.tar.gz && \
    cd jsonnet-0.9.5 && \
    make && \
    mv jsonnet /usr/local/bin && \
    rm -rf /tmp/v0.9.5.tar.gz && \
    rm -rf /tmp/jsonnet-0.9.5

COPY ./Pipfile ./Pipfile.lock /tmp/

# Install various python libraries for both Python 2 and 3 (for now)
# Don't upgrade pip for now because it seems to be broken
# https://github.com/pypa/pip/issues/5240
RUN cd /tmp/ && \
    pip2 install -U wheel && \
    pip2 install pipenv && \
    pipenv install --system --two && \
    pip3 install -U wheel && \
    pip3 install pipenv && \
    pipenv install --system --three

COPY checkout.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/checkout.sh

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

# Add the directory where we will checkout kubeflow/testing
# which contains shared scripts.
ENV PYTHONPATH /src/kubeflow/testing/py

ENTRYPOINT ["/usr/local/bin/run_workflows.sh"]
