"""Utilities used by our python scripts for building and releasing."""
import datetime
import logging
import os
import re
import six
import subprocess
import time
import yaml

from kubernetes.config import kube_config
from kubernetes.client import configuration as kubernetes_configuration

import boto3


def run(command, cwd=None, env=None, polling_interval=datetime.timedelta(seconds=1)):
    """Run a subprocess.

    Any subprocess output is emitted through the logging modules.

    Returns:
      output: A string containing the output.
    """
    logging.info("Running: %s \ncwd=%s", " ".join(command), cwd)

    if not env:
        env = os.environ
    else:
        keys = sorted(env.keys())

        lines = []
        for k in keys:
            lines.append("{0}={1}".format(k, env[k]))
        logging.info("Running: Environment:\n%s", "\n".join(lines))

    process = subprocess.Popen(
        command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )

    logging.info("Subprocess output:\n")
    output = []
    while process.poll() is None:
        process.stdout.flush()
        for line in iter(process.stdout.readline, b""):
            if six.PY2:
                line = line.strip()
            else:
                line = line.decode().strip()

            output.append(line)
            logging.info(line)

        time.sleep(polling_interval.total_seconds())

    process.stdout.flush()
    for line in iter(process.stdout.readline, b""):
        if six.PY2:
            line = line.strip()
        else:
            line = line.decode().strip()
        output.append(line)
        logging.info(line)

    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode,
            "cmd: {0} exited with code {1}".format(
                " ".join(command), process.returncode
            ),
            "\n".join(output),
        )

    return "\n".join(output)


def to_s3_uri(bucket, path):
    """Convert bucket and path to a S3 URI."""
    return "s3://" + os.path.join(bucket, path)


S3_REGEX = re.compile("s3://([^/]*)(/.*)?")


def split_s3_uri(s3_uri):
    """Split a S3 URI into bucket and path."""
    m = S3_REGEX.match(s3_uri)
    bucket = m.group(1)
    path = ""
    if m.group(2):
        path = m.group(2).lstrip("/")
    return bucket, path


# TODO(jlewi): This was originally a work around for
# https://github.com/kubernetes-incubator/client-python/issues/339.
#
# There was a fix (see issue) that sets the scope but userinfo.email scope
# wasn't included. Which I think will cause problems see
# https://github.com/kubernetes-client/python-base/issues/54
#
# So as a work around we use this function to allow us to specify the scopes.
#
# This function is based on
# https://github.com/kubernetes-client/python-base/blob/master/config/kube_config.py#L331
# we modify it though so that we can pass through the function to get credentials.
def load_kube_config(
    config_file=None,
    context=None,
    client_configuration=None,
    persist_config=True,
    get_google_credentials=None,
    print_config=False,
    **kwargs
):
    """Loads authentication and cluster information from kube-config file
    and stores them in kubernetes.client.configuration.

    :param config_file: Name of the kube-config file.
    :param context: set the active context. If is set to None, current_context
        from config file will be used.
    :param client_configuration: The kubernetes.client.ConfigurationObject to
        set configs to.
    :param persist_config: If True, config file will be updated when changed
        (e.g GCP token refresh).
    """

    if config_file is None:
        config_file = os.path.expanduser(kube_config.KUBE_CONFIG_DEFAULT_LOCATION)
    logging.info("Using Kubernetes config file: %s", config_file)

    config_persister = None
    if persist_config:

        def _save_kube_config(config_map):
            with open(config_file, "w") as f:
                yaml.safe_dump(config_map, f, default_flow_style=False)

        config_persister = _save_kube_config

    loader = kube_config._get_kube_config_loader_for_yaml_file(  # pylint: disable=protected-access
        config_file,
        active_context=context,
        config_persister=config_persister,
        get_google_credentials=get_google_credentials,
        **kwargs
    )

    if client_configuration is None:
        config = type.__call__(kubernetes_configuration.Configuration)
        loader.load_and_set(config)  # pylint: disable=too-many-function-args
        kubernetes_configuration.Configuration.set_default(config)
    else:
        loader.load_and_set(
            client_configuration
        )  # pylint: disable=too-many-function-args
    # Dump the loaded config.

    # Warning this will print out any access tokens stored in your kubeconfig
    if print_config:
        run(["kubectl", "config", "view"])


def aws_configure_credential():
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        logging.info("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set;")
    else:
        logging.info("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are not set.")
    run(["aws", "eks", "update-kubeconfig", "--name=" + os.getenv("AWS_EKS_CLUSTER")])


def upload_to_s3(contents, target, file_name):
    """Uploading contents to s3"""
    s3 = boto3.resource("s3")
    bucket_name, path = split_s3_uri(target)
    with open(file_name, "w+") as data:
        data.write(contents)
    logging.info("Uploading file %s to %s.", file_name, target)
    s3.meta.client.upload_file(file_name, bucket_name, path)


def upload_file_to_s3(source, target):
    s3 = boto3.resource("s3")
    bucket_name, path = split_s3_uri(target)
    logging.info("Uploading file %s to %s.", source, target)
    s3.meta.client.upload_file(source, bucket_name, path)
