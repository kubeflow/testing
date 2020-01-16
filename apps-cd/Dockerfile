FROM ubuntu:18.04

RUN apt-get update -y && \
    apt-get install -y curl git python3.8 python3-pip && \
    ln -sf /usr/bin/python3.8 /usr/bin/python

# Install the hub CLI for git
RUN cd /tmp && \
    curl -LO  https://github.com/github/hub/releases/download/v2.13.0/hub-linux-amd64-2.13.0.tgz && \
    tar -xvf hub-linux-amd64-2.13.0.tgz && \
    mv hub-linux-amd64-2.13.0 /usr/local && \
    ln -sf /usr/local/hub-linux-amd64-2.13.0/bin/hub /usr/local/bin/hub

RUN python -m pip install fire \
     google-api-python-client \
     google-cloud-storage \
     kubernetes \
     watchdog

RUN mkdir -p /app
COPY update_launcher.py /app
COPY run_with_auto_restart.py /app