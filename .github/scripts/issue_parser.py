#!/usr/bin/env python3
"""AI Issue Analyzer - Validates and classifies issue titles for Kubeflow ."""

import json
import os
import re
import subprocess
import sys
import uuid


def validate_title_pattern(title, pattern=None):
    """
    Validate the issue title matches the required pattern.

    Args:
        title: The issue title to validate
        pattern: Optional regex pattern to use for validation

    Returns:
        tuple: (is_valid, issue_type, issue_area) where is_valid is bool
    """
    if pattern is None:
        pattern = r'^(bug|chore|feat)\(([a-z]+)\):\s*(\S.*)$'

    match = re.match(pattern, title)

    if not match:
        return False, None, None

    issue_type = match.group(1)
    issue_area = match.group(2)

    return True, issue_type, issue_area


def build_reference_standards(issue_type, issue_samples_json):
    """Select an issue type's reference sample from a JSON string.

    The JSON must be an object mapping issue types to nonempty strings.
    Missing types use the generic review rubric. Invalid configuration raises
    ValueError instead of silently discarding the supplied samples.
    """
    samples = json.loads(issue_samples_json)
    if not isinstance(samples, dict) or any(
        not isinstance(sample, str) or not sample.strip()
        for sample in samples.values()
    ):
        raise ValueError("ISSUE_SAMPLES must be a JSON object mapping issue types to nonempty strings")

    return samples.get(
        issue_type,
        "No directly comparable approved reference is available; evaluate only against the review rubric.",
    )


def post_invalid_title_comment(issue_number, repository):
    """
    Post a comment for an invalid issue title.

    Args:
        issue_number: The GitHub issue number
        repository: The GitHub repository (owner/repo format)
    """
    comment_body = (
        "## 🤖 AI Issue Quality Review\\n\\n"
        "⚠️ **Validation Failed:** Issue title must follow the correct format: "
        "`<type>(<area>): <title contents>`, where type is `bug`, `chore`, or `feat`."
    )

    subprocess.run(
        ["gh", "issue", "comment", str(issue_number), "--repo", repository, "--body", comment_body],
        check=True
    )


def write_github_output(key, value):
    """
    Write output to GitHub Actions output file.

    Args:
        key: The output key
        value: The output value
    """
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            if "\n" in value or "\r" in value:
                delimiter = f"gh_output_{uuid.uuid4().hex}"
                f.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{key}={value}\n")


def main():
    """Main execution function."""
    issue_title = os.environ.get("ISSUE_TITLE", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "")
    github_repository = os.environ.get("REPO") or os.environ.get("GITHUB_REPOSITORY", "")
    title_pattern = os.environ.get("TITLE_PATTERN") or None
    issue_samples_json = os.environ.get("ISSUE_SAMPLES", "{}")

    # Validate the title
    is_valid, issue_type, issue_area = validate_title_pattern(issue_title, title_pattern)

    if not is_valid:
        post_invalid_title_comment(issue_number, github_repository)
        write_github_output("valid", "false")
        return 0

    # Build reference standards
    reference_standards = build_reference_standards(issue_type, issue_samples_json)

    # Write outputs
    write_github_output("valid", "true")
    write_github_output("issue_type", issue_type)
    write_github_output("issue_area", issue_area)
    write_github_output("reference_standards", reference_standards)

    return 0


if __name__ == "__main__":
    sys.exit(main())
