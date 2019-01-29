# Docker image to snapshot repo commit hash used for nightly deployment.

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

# Use Pipfile to manage Python deps.
COPY ./Pipfile ./Pipfile.lock /tmp/

RUN cd /tmp/ && \
    pip2 install -U wheel filelock && \
    pip2 install pipenv && \
    pipenv install --system --two && \
    pip3 install -U wheel filelock

RUN pip3 install pipenv==2018.10.9
RUN cd /tmp/ && pipenv install --system --three

COPY snapshot_kf_deployment.py /usr/local/bin
