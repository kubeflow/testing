#!/usr/bin/python
"""Post status back from an argo-workflow

Requires Prow environment variables to post back status
"""

import argparse
import json
import logging
import os
import requests

# Repo org and name can be set via environment variables when running
# on PROW. But we choose sensible defaults so that we can run locally without
# setting defaults.
REPO_ORG = os.getenv("REPO_OWNER", "tensorflow")
REPO_NAME = os.getenv("REPO_NAME", "k8s")

class Github(object):
  def __init__(self, oauth):
    self.github_api = 'https://api.github.com'
    self.oauth = oauth
    if self.oauth is None:
      raise Exception('Missing environment variable GIT_TOKEN')
    self.headers = {
        'Authorization': 'token {}'.format(self.oauth),
        'Content-Type': 'application/json'
    }

  def request(self, verb, url, data=None):
    if verb == 'get':
      resp = requests.get(url, headers=self.headers)
    elif verb == 'post':
      resp = requests.post(url, headers=self.headers, data=data)

    if 200 <= resp.status_code < 300:
      return resp.json()
    else:
      log_request_failure = "{} {} request failed\n{}".format(url, verb, resp.text)
      logging.info(log_request_failure)

  def get(self, url):
    return self.request('get', url)

  def post(self, url, data):
    return self.request('post', url, data=data)

class GithubStatus(Github):
  # https://developer.github.com/v3/repos/statuses
  def __init__(self):
    Github.__init__(self)

  def format_url(self, url, owner=None, repo=None, sha=None):
    if owner is None:
      owner = REPO_ORG
    if repo is None:
      repo = REPO_NAME
    if sha is None:
      sha = os.environ.get('PULL_PULL_SHA')

    return url.format(
      self.github_api, owner, repo, sha
    )

  def create_status(self, state, target_url, description, context,
                      url=None, owner=None, repo=None, sha=None):
    # https://developer.github.com/v3/repos/statuses/#create-a-status
    # POST /repos/:owner/:repo/statuses/:sha
    if url is None:
      url = self.format_url('{}/repos/{}/{}/statuses/{}',
                            owner=owner, repo=repo, sha=sha)

    data = json.dumps({
            'state': state,
            'target_url': target_url,
            'description': description,
            'context': context
    })
    log_status = 'Updating status for commit {}:\n{}'.format(url, data)
    logging.info(log_status)
    return self.post(url, data)
