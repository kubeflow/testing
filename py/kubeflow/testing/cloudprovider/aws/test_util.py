import unittest

from kubeflow.testing.cloudprovider.aws import util


class AwsUtilTest(unittest.TestCase):
    def test_run(self):
        cmd, env, cwd = ["echo", "helloWorld"], None, None

        self.assertEqual("helloWorld", util.run(cmd, env, cwd))

    def test_to_s3_uri(self):
        bucket = "fakeBucket"
        path = "fakePath/folder1/folder2/hello.txt"

        self.assertEqual(
            "s3://fakeBucket/fakePath/folder1/folder2/hello.txt",
            util.to_s3_uri(bucket, path),
        )

    def test_split_s3_uri(self):
        s3_uri = "s3://fakeBucket/fakePath/folder1/folder2/hello.txt"
        self.assertEqual(
            ("fakeBucket", "fakePath/folder1/folder2/hello.txt"),
            util.split_s3_uri(s3_uri),
        )

        with self.assertRaises(AttributeError):
            s3_uri = "s3:fakeBucket/fakePath/folder1/folder2/hello.txt"
            self.assertEqual(
                ("fakeBucket", "fakePath/folder1/folder2/hello.txt"),
                util.split_s3_uri(s3_uri),
            )
