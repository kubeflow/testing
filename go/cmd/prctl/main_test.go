package main

import "testing"

func TestErrorRegexes(t *testing.T) {
	type testCase struct {
		errorRes map[string][]string
		text string
		expected string
	}

	cases := []testCase {
		{
			errorRes: gitErrorRegexes,
			text: `On branch update-0703
Your branch is ahead of 'origin/master' by 1 commit.
  (use "git push" to publish your local commits)

nothing to commit, working tree clean`,
			expected:NothingToCommit,
		},
	}

	for _, c := range cases {
		m, err := matchRePatterns(c.errorRes, c.text)

		if err != nil {
			t.Errorf("Unexpected error; %v", err)
			continue
		}

		if m != c.expected {
			t.Errorf("Got %v; Want %v", m, c.expected)
		}
	}
}
