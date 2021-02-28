import re

from kubeflow.testing.cloudprovider.aws import util

S3_REGEX = re.compile("s3://([^/]*)(/.*)?")


def test_run():
    cmd, env, cwd = ["echo", "helloWorld"], None, None

    assert "helloWorld" == util.run(cmd, env, cwd)


def test_to_s3_uri():
    bucket = "fakeBucket"
    path = "fakePath/folder1/folder2"

    assert "s3://fakeBucket/fakePath/folder1/folder2" == util.to_s3_uri(bucket, path)


def test_split_s3_uri():
    s3_uri = "s3://fakeBucket/fakePath/folder1/folder2"

    assert "fakeBucket", "fakePath/folder1/folder2" == util.split_s3_uri(s3_uri)
