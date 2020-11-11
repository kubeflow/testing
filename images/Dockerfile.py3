# Build the docker image used to run the scripts
# to continuously update our docker files.
#
# The context for this docker file should be the root of the kubeflow/testing repository.
FROM ubuntu:18.04

RUN apt-get update -y && \
    apt-get install -y curl git python3.8 python3-distutils wget && \
    ln -sf /usr/bin/python3.8 /usr/bin/python && \
    ln -sf /usr/bin/python3.8 /usr/bin/python3

RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && python get-pip.py

RUN python3.8 -m pip install \
    filelock \
    fire \
    google-api-python-client \
    google-cloud \
    google-cloud-storage \
    junit-xml \
    # See https://github.com/kubeflow/gcp-blueprints/issues/52#issuecomment-645446088
    # our libs seem to break with 11.0.0
    kubernetes==12.0.0 \
    lint \
    oauth2client \
    pytest==5.4 \
    pytest-timeout==1.4 \
    python-dateutil \
    retrying \
    watchdog

# Install go
RUN cd /tmp && \
    wget -O /tmp/go.tar.gz https://dl.google.com/go/go1.14.2.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go.tar.gz

# Install gcloud
ENV PATH=/root/go/bin:/usr/local/go/bin:/google-cloud-sdk/bin:/workspace:${PATH} \
    CLOUDSDK_CORE_DISABLE_PROMPTS=1

# Install the new version of yq which is based on go
RUN GO111MODULE=on go get github.com/mikefarah/yq/v3
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

RUN gcloud components install anthoscli kpt

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

RUN export ASM_VERSION=1.4.7-asm.0 && \
    cd /tmp && \
    curl -LO https://storage.googleapis.com/gke-release/asm/istio-${ASM_VERSION}-linux.tar.gz && \
    tar -xvf istio-${ASM_VERSION}-linux.tar.gz && \
    mv istio-${ASM_VERSION} /usr/local && \
    ln -sf /usr/local/istio-${ASM_VERSION}/bin/istioctl /usr/local/bin/istioctl

    
# Create go symlinks
RUN ln -sf /usr/local/go/bin/go /usr/local/bin && \
    ln -sf /usr/local/go/bin/gofmt /usr/local/bin && \
    ln -sf /usr/local/go/bin/godoc /usr/local/bin

RUN go get github.com/kelseyhightower/kube-rsa

COPY ./images/checkout_repos.sh /usr/local/bin
COPY ./images/checkout.sh /usr/local/bin
COPY ./images/setup_ssh.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/checkout* /usr/local/bin/setup_ssh.sh

COPY ./images/run_workflows.sh /usr/local/bin
RUN chmod a+x /usr/local/bin/run_workflows.sh

COPY ./images/run_release.sh /usr/local/bin
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

RUN go get -u github.com/jstemmer/go-junit-report

# Create a cached copy of the python test scripts so that we don't
# need to clone the repo just to get access to them
RUN mkdir -p /srcCache/kubeflow/testing
COPY py /srcCache/kubeflow/testing/py
COPY notebook_testing /srcCache/kubeflow/testing/notebook_testing

ENTRYPOINT ["/usr/local/bin/run_workflows.sh"]