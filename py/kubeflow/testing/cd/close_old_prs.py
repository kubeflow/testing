"""If there are multiple PRs open to update an app; close the older ones"""

import collections
from dateutil import parser as date_parser
import fire
import json
import logging
import re

from code_intelligence import graphql

# The name of the GitHub user under which kubeflow-bot branches exist
KUBEFLOW_BOT = "kubeflow-bot"

# This needs to be in sync with the pattern used in create_manifests_pr
# The pattern should be "update_{image.name}_{image.tag}"
# TODO(jlewi): What if there are underscores in the image name
HEAD_PATTERN = re.compile("update_([^_]+)_([^_]+)-([^_]+)")

APP_TAG = collections.namedtuple("APP_TAG", ("app", "tag"))
class PRCloser:

  def __init__(self):
    self._client = graphql.GraphQLClient()

  def apply(self):
    app_prs = collections.defaultdict(lambda: [])

    for pr in self._iter_prs("kubeflow", "manifests"):
      login = pr["author"]["login"]
      if login == KUBEFLOW_BOT:
        m = HEAD_PATTERN.match(pr["headRefName"])

        if not m:
          url = pr["url"]
          logging.error(f"PR: {url} has ref {pr['headRefName']} which doesn't "
                        f"match pattern {HEAD_PATTERN.pattern}")
          continue

        app = APP_TAG(m.group(1), m.group(2))
        app_prs[app] = app_prs[app] + [pr]

    # For each application and tuple close all but the most recent PRs
    for app, prs in app_prs.items():
      logging.info(f"{app} has {len(prs)} open prs")
      if len(prs) == 1:
        continue

      # We sort the PRs by URL since this will correspond to PR number
      # We will keep the most recent one.
      sorted_prs = sorted(prs, key=lambda pr: pr["url"])

      latest = sorted_prs[-1]
      logging.info(f"For app_tag={app} newest pr is {latest['url']}")

      for p in sorted_prs[:-1]:
        logging.info(f"Closing pr {p['url']}")
        add_comment = """
    mutation AddComment($input: AddCommentInput!){
      addComment(input:$input) {
         clientMutationId
      }
    }
    """
        message = f"""
* There is a newer pr, {latest['url']}, to update the application
* Closing this PR
"""
        add_variables = {
          "input": {
            "body": message,
            "subjectId": p["id"],
          }
        }

        results = self._client.run_query(add_comment, variables=add_variables)

        if results.get("errors"):
          message = json.dumps(results.get("errors"))
          logging.error(f"There was a problem adding the comment; errors:\n{message}\n")


        close_pr = """
      mutation ClosePullRequest($input: ClosePullRequestInput!){
        closePullRequest(input:$input) {
           clientMutationId
        }
      }
      """

        close_variables = {
          "input": {
            "pullRequestId": p["id"],
          }
        }

        results = self._client.run_query(close_pr, variables=close_variables)

        if results.get("errors"):
          message = json.dumps(results.get("errors"))
          logging.error(f"There was a problem closing the pull request {p['url']}; "
                        f"errors:\n{message}\n")

  def _iter_prs(self, org, repo):
    """Iterate over open PRs in the specified repo.

    Args:
      org: The org that owns the repository
      repo: The directory for the repository
      issue_filter: Used to filter issues to consider based on when they were
        last updated

    Writes the issues along with the first comments to a file in output
    directory.
    """
    num_prs_per_page = 25
    query = """query getIssues($org: String!, $repo: String!, $pageSize: Int, $issueCursor: String,) {
  repository(owner: $org, name: $repo) {
    pullRequests(first: $pageSize, after: $issueCursor, states: [OPEN]) {
      totalCount
      pageInfo {
        endCursor
        hasNextPage
      }
      edges {
        node {
          author {
            __typename
            ... on User {
              login
            }
            ... on Bot {
              login
            }
          }
          id
          title
          url
          state
          headRefName
          createdAt
          closedAt
          labels(first: 30) {
            totalCount
            edges {
              node {
                name
              }
            }
          }
        }
      }
    }
  }
}
"""

    total_prs = None
    has_next_prs_page = True
    # TODO(jlewi): We should persist the cursors to disk so we can resume
    # after errors
    prs_cursor = None

    while has_next_prs_page:

      variables = {
        "org": org,
        "repo": repo,
        "pageSize": num_prs_per_page,
        "issueCursor": prs_cursor,
      }
      results = self._client.run_query(query, variables=variables)

      if results.get("errors"):
        message = json.dumps(results.get("errors"))
        logging.error(f"There was a problem issuing the query; errors:\n{message}\n")
        return

      if not total_prs:
        total_prs = results["data"]["repository"]["pullRequests"]["totalCount"]
        logging.info("%s/%s has a total of %s pullRequests", org, repo, total_prs)

      prs = graphql.unpack_and_split_nodes(
        results, ["data", "repository", "pullRequests", "edges"])
      for pr in prs:
        yield pr

      page_info = results["data"]["repository"]["pullRequests"]["pageInfo"]
      prs_cursor = page_info["endCursor"]
      has_next_prs_page = page_info["hasNextPage"]


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO,
                      format=('%(levelname)s|%(asctime)s'
                              '|%(pathname)s|%(lineno)d| %(message)s'),
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      )
  logging.getLogger().setLevel(logging.INFO)
  fire.Fire(PRCloser)
