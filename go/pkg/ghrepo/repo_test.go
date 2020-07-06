package ghrepo

import "testing"

func Test_FromUrlOrName(t *testing.T) {
	type testCase struct {
		in string
		expectedOwner string
		expectedName string
	}

	cases := []testCase{
		{
			in: "kubeflow/code",
			expectedOwner: "kubeflow",
			expectedName: "code",
		},
		{
			in: "git@github.com:kubeflow/code.git",
			expectedOwner: "kubeflow",
			expectedName: "code",
		},
		{
			in: "https://github.com/kubeflow/code.git",
			expectedOwner: "kubeflow",
			expectedName: "code",
		},
	}

	for _, c := range cases {
		r, err := FromUrlOrName(c.in)

		if err != nil {
			t.Errorf("in: %v; Got error: %v", c.in, err)
			continue
		}

		if r.RepoOwner() != c.expectedOwner {
			t.Errorf("in %v; Got %v want %v", c.in, r.RepoOwner(), c.expectedOwner)
		}
		if r.RepoName() != c.expectedName {
			t.Errorf("in %v; Got %v want %v", c.in, r.RepoName(), c.expectedName)
		}
	}
}
