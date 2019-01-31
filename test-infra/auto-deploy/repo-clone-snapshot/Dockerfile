FROM ubuntu:xenial
MAINTAINER Gabriel Wen

# Never prompt the user for choices on installation/configuration of packages
ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=linux
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Install basic packages.
RUN set -ex \
    && apt-get update -yqq \
    && apt-get install -yqq --no-install-recommends \
    git \
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

# # Install go
# RUN cd /tmp && \
#     wget -O /tmp/go.tar.gz https://redirector.gvt1.com/edgedl/go/go1.9.2.linux-amd64.tar.gz && \
#     tar -C /usr/local -xzf go.tar.gz
# 
# # Install gcloud
# ENV PATH=/usr/local/go/bin:/google-cloud-sdk/bin:/workspace:${PATH} \
#     CLOUDSDK_CORE_DISABLE_PROMPTS=1
# 
# RUN wget -q https://dl.google.com/dl/cloudsdk/channels/rapid/google-cloud-sdk.tar.gz && \
#     tar xzf google-cloud-sdk.tar.gz -C / && \
#     rm google-cloud-sdk.tar.gz && \
#     /google-cloud-sdk/install.sh \
#     --disable-installation-options \
#     --bash-completion=false \
#     --path-update=false \
#     --usage-reporting=false && \
#     gcloud components install alpha beta


# Use Pipfile to manage Python deps.
COPY ./Pipfile ./Pipfile.lock /tmp/

RUN cd /tmp/ && \
    pip2 install -U wheel filelock && \
    pip2 install pipenv && \
    pipenv install --system --two && \
    pip3 install -U wheel filelock

RUN pip3 install pipenv==2018.10.9
RUN cd /tmp/ && pipenv install --system --three

COPY repo-clone-snapshot.py /usr/local/bin
COPY checkout-snapshot.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/checkout-snapshot.sh
