# Copyright The Kubeflow Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Run with: python -m unittest discover -s .github/scripts -p 'test_*.py'."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import issue_parser


FALLBACK = (
    "No directly comparable approved reference is available; "
    "evaluate only against the review rubric."
)


class TitleValidationTests(unittest.TestCase):
    def test_supported_types_and_areas(self):
        for issue_type, area in (("bug", "backend"), ("feat", "sdk"), ("chore", "frontend")):
            with self.subTest(issue_type=issue_type):
                self.assertEqual(
                    issue_parser.validate_title_pattern(f"{issue_type}({area}): Useful description"),
                    (True, issue_type, area),
                )

    def test_invalid_titles(self):
        for title in (
            "", "plain title", "fix(sdk): Description", "BUG(sdk): Description",
            "bug(SDK): Description", "bug(): Description", "bug(sdk2): Description",
            "bug(sdk) Description", "bug(sdk):", "bug(sdk):   ",
            "prefix bug(sdk): Description",
        ):
            with self.subTest(title=title):
                self.assertEqual(issue_parser.validate_title_pattern(title), (False, None, None))

    def test_unicode_description(self):
        self.assertEqual(
            issue_parser.validate_title_pattern("bug(sdk): 修复 Unicode 🐛"),
            (True, "bug", "sdk"),
        )

    def test_custom_pattern(self):
        pattern = r"^(fix|docs)\[([a-z-]+)\]: (.+)$"
        self.assertEqual(
            issue_parser.validate_title_pattern("docs[api-docs]: Update examples", pattern),
            (True, "docs", "api-docs"),
        )
        self.assertEqual(
            issue_parser.validate_title_pattern("bug(sdk): Description", pattern),
            (False, None, None),
        )


class ReferenceStandardsTests(unittest.TestCase):
    def test_selects_matching_entry(self):
        samples = {"bug": "Bug example", "feat": "Feature example", "chore": "Maintenance example"}
        for issue_type, sample in samples.items():
            with self.subTest(issue_type=issue_type):
                self.assertEqual(
                    issue_parser.build_reference_standards(issue_type, json.dumps(samples)), sample,
                )

    def test_missing_type_uses_fallback(self):
        for samples in ({}, {"feat": "Feature example"}, {"BUG": "Uppercase key"}):
            with self.subTest(samples=samples):
                self.assertEqual(
                    issue_parser.build_reference_standards("bug", json.dumps(samples)), FALLBACK,
                )

    def test_preserves_sample_text(self):
        sample = '  Example 🐛 with "quotes" and \\slashes\nvalid=false\r\nLast line  '
        self.assertEqual(
            issue_parser.build_reference_standards("bug", json.dumps({"bug": sample})), sample,
        )

    def test_custom_issue_type(self):
        self.assertEqual(
            issue_parser.build_reference_standards("docs", '{"docs": "Documentation example"}'),
            "Documentation example",
        )

    def test_malformed_json(self):
        for value in ("", "not json", "{'bug': 'Example'}", '{"bug": "Example",}'):
            with self.subTest(value=value), self.assertRaises(json.JSONDecodeError):
                issue_parser.build_reference_standards("bug", value)

    def test_non_object_json(self):
        for value in (None, [], ["Example"], "Example", 1, True):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "JSON object"):
                issue_parser.build_reference_standards("bug", json.dumps(value))

    def test_invalid_sample_values_even_for_unselected_types(self):
        for value in (None, True, 42, [], {}, "", " \n\t"):
            for key in ("bug", "feat"):
                with self.subTest(value=value, key=key), self.assertRaisesRegex(ValueError, "nonempty strings"):
                    issue_parser.build_reference_standards("bug", json.dumps({key: value}))


class OutputAndMainTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name) / "output"
        env = patch.dict(os.environ, {
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_REPOSITORY": "example/consumer",
            "ISSUE_NUMBER": "42",
            "ISSUE_TITLE": "feat(sdk): Add support",
            "ISSUE_SAMPLES": '{"feat": "Consumer feature sample"}',
        }, clear=True)
        env.start()
        self.addCleanup(env.stop)
        run = patch.object(issue_parser.subprocess, "run")
        self.run = run.start()
        self.addCleanup(run.stop)

    def test_single_line_outputs_append(self):
        issue_parser.write_github_output("valid", "true")
        issue_parser.write_github_output("reference_standards", "Text with = sign")
        self.assertEqual(self.output.read_text(), "valid=true\nreference_standards=Text with = sign\n")

    def test_multiline_output_is_one_value(self):
        for value in ("First\nvalid=false\nLast", "First\rLast", "First\r\nLast\n"):
            with self.subTest(value=value):
                self.output.write_text("")
                issue_parser.write_github_output("reference_standards", value)
                header, payload = self.output.read_bytes().decode().split("\n", 1)
                key, delimiter = header.split("<<", 1)
                self.assertEqual(key, "reference_standards")
                self.assertTrue(delimiter)
                self.assertNotIn(delimiter, value.splitlines())
                self.assertEqual(payload, f"{value}\n{delimiter}\n")

    def test_output_without_github_environment_is_noop(self):
        del os.environ["GITHUB_OUTPUT"]
        issue_parser.write_github_output("valid", "true")
        self.assertFalse(self.output.exists())

    def test_output_io_errors_propagate(self):
        os.environ["GITHUB_OUTPUT"] = str(self.output / "missing" / "output")
        with self.assertRaises(OSError):
            issue_parser.write_github_output("valid", "true")

    def test_valid_issue_main(self):
        self.assertEqual(issue_parser.main(), 0)
        self.assertEqual(self.output.read_text(), (
            "valid=true\nissue_type=feat\nissue_area=sdk\n"
            "reference_standards=Consumer feature sample\n"
        ))
        self.run.assert_not_called()

    def test_main_without_samples_uses_fallback(self):
        del os.environ["ISSUE_SAMPLES"]
        self.assertEqual(issue_parser.main(), 0)
        self.assertIn(f"reference_standards={FALLBACK}\n", self.output.read_text())
        self.run.assert_not_called()

    def test_main_honors_custom_pattern(self):
        os.environ.update({
            "TITLE_PATTERN": r"^(docs)\[([a-z]+)\]: (.+)$",
            "ISSUE_TITLE": "docs[api]: Explain usage",
            "ISSUE_SAMPLES": '{"docs": "Documentation sample"}',
        })
        self.assertEqual(issue_parser.main(), 0)
        self.assertIn("issue_type=docs\nissue_area=api\n", self.output.read_text())
        self.assertIn("reference_standards=Documentation sample\n", self.output.read_text())

    def test_invalid_title_comments_on_caller_repository(self):
        os.environ["ISSUE_TITLE"] = '$(touch unexpected); invalid title'
        self.assertEqual(issue_parser.main(), 0)
        self.assertEqual(self.output.read_text(), "valid=false\n")
        self.run.assert_called_once()
        args = self.run.call_args.args[0]
        self.assertEqual(args[:7], ["gh", "issue", "comment", "42", "--repo", "example/consumer", "--body"])
        self.assertIn("Validation Failed", args[7])
        self.assertNotIn(os.environ["ISSUE_TITLE"], args[7])
        self.assertEqual(self.run.call_args.kwargs, {"check": True})

    def test_explicit_repo_is_used_for_validation_comment(self):
        os.environ["ISSUE_TITLE"] = "invalid"
        os.environ["REPO"] = "example/explicit-repo"
        self.assertEqual(issue_parser.main(), 0)
        self.assertEqual(self.run.call_args.args[0][4:6], ["--repo", "example/explicit-repo"])

    def test_empty_repo_and_pattern_use_defaults(self):
        os.environ.update(REPO="", TITLE_PATTERN="")
        self.assertEqual(issue_parser.main(), 0)
        self.assertIn("valid=true\n", self.output.read_text())

    def test_comment_failure_does_not_write_success_outputs(self):
        os.environ["ISSUE_TITLE"] = "invalid"
        self.run.side_effect = subprocess.CalledProcessError(1, "gh")
        with self.assertRaises(subprocess.CalledProcessError):
            issue_parser.main()
        self.assertFalse(self.output.exists())

    def test_bad_sample_configuration_does_not_write_outputs_or_comment(self):
        for value in ("not json", "[]", '{"feat": 42}'):
            with self.subTest(value=value):
                os.environ["ISSUE_SAMPLES"] = value
                with self.assertRaises(ValueError):
                    issue_parser.main()
                self.assertFalse(self.output.exists())
                self.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
