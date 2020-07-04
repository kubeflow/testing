package main

import (
	"github.com/onrik/logrus/filename"
	"github.com/pkg/errors"
	log "github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"os/exec"
	"regexp"
)

var (
	rootCmd = &cobra.Command{
		Use:   "prctl",
		Short: "A CLI to help with creating PRs",
		Long:  `prctl is a CLI to help create PRs as part of GitOps workflows`,
	}

	upstreamName string
	repoDir string
	forkName string
	fork string
	branchName string
	messagePath string
	baseBranch string

	branchCmd = &cobra.Command{
		Use:   "branch",
		Short: "Create a branch to be used for creating PRs.",
		Long:  `prctl branch creates a branch on a remote repo to contain any changes`,
		Run: func(cmd *cobra.Command, args []string) {
			err := branch(repoDir, upstreamName, forkName, fork, branchName)

			if err != nil {
				log.Fatalf("branch failed; error: %+v", err)
			}
		},
	}

	pushCmd = &cobra.Command{
		Use:   "push",
		Short: "Commit changes and push them.",
		Long:  `prctl push commit changes and push them`,
		Run: func(cmd *cobra.Command, args []string) {
			err := push(repoDir, forkName, branchName, messagePath)

			if err != nil {
				log.Fatalf("push failed; error: %+v", err)
			}
		},
	}

	prCmd = &cobra.Command{
		Use:   "pull-request",
		Short: "Create a PR in GitHub.",
		Long:  `prctl pull-request creates a PR`,
		Run: func(cmd *cobra.Command, args []string) {
			err := pr(repoDir, baseBranch, messagePath)

			if err != nil {
				log.Fatalf("push failed; error: %+v", err)
			}
		},
	}
)

func init() {
	rootCmd.AddCommand(branchCmd)
	rootCmd.AddCommand(pushCmd)
	rootCmd.AddCommand(prCmd)

	branchCmd.Flags().StringVarP(&upstreamName, "upstreamName", "", "origin", "The name of the remote repository corresponding to the upstream URL")
	branchCmd.Flags().StringVarP(&repoDir, "repoDir", "", "", "Directory where the code is checked out")
	branchCmd.Flags().StringVarP(&forkName, "forkName", "", "", "Name to assign the remote repo for the fork")
	branchCmd.Flags().StringVarP(&fork, "fork", "", "", "Name to assign the remote repo for the fork")
	branchCmd.Flags().StringVarP(&branchName, "branchName", "", "", "Name to the branch to create")

	pushCmd.Flags().StringVarP(&repoDir, "repoDir", "", "", "Directory where the code is checked out")
	pushCmd.Flags().StringVarP(&forkName, "forkName", "", "", "Name to assign the remote repo for the fork")
	pushCmd.Flags().StringVarP(&branchName, "branchName", "", "", "Name to the branch to create")
	pushCmd.Flags().StringVarP(&messagePath, "messagePath", "", "", "Path to a file containing the message to use for the commit")

	prCmd.Flags().StringVarP(&repoDir, "repoDir", "", "", "Directory where the code is checked out")
	prCmd.Flags().StringVarP(&baseBranch, "baseBranch", "", "kubeflow:master", "Name of the branch to use as the base")
	prCmd.Flags().StringVarP(&messagePath, "messagePath", "", "", "Path to a file containing the message to use for the commit")

	// Add filename as one of the fields of the structured log message.
	filenameHook := filename.NewHook()
	filenameHook.Field = "filename"
	log.AddHook(filenameHook)
}

// execHelper is a helper class for running some shell commands.
type execHelper struct {
	// cmd is the command to execute
	cmd *exec.Cmd
	// errorRes is a map from an id (an arbitrary) string to a list of regexes for errors
	// if the regexes match stderr then the corresponding id will be returned in run
	errorRes map[string][]string
}

// Run the specified command.
// Returns the id of the error that matched if any; the empty string otherwise.
// error non nil if an unmatched exception occur.
func (e *execHelper) Run() (string, error) {
	out, err := e.cmd.Output()

	if err != nil {

		exitError, ok := err.(*exec.ExitError)

		if !ok{
			return "", errors.WithStack(err)
		}

		log.Infof("Output of %v; %v", e.cmd.String(), string(exitError.Stderr))
		for eid, patterns := range e.errorRes {
			for _, re := range patterns {
				match, err := regexp.MatchString(re, string(exitError.Stderr))

				if err != nil {
					return "", errors.WithStack(err)
				}

				if match {
					return eid, nil
				}
			}
		}

		return "", err
	}
	log.Infof("Output of %v; %v", e.cmd.String(), string(out))

	return "", nil
}

// branch creates a branch for all the changes
func branch( repoDir string, upstreamName string, forkName string, forkUrl string, branchName string) error {
	e := &execHelper{
		cmd: exec.Command("git", "fetch", "--unshallow"),
		errorRes: map[string][]string {
			"unshallow": []string{".*unshallow on a complete repository.*"},
		},
	}

	e.cmd.Dir = repoDir

	_, err := e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was a problem unshallowing the repo.")
	}

	// Create a new branch for the pull request.
	e = &execHelper{
		cmd: exec.Command("git", "checkout", "-b", branchName, upstreamName + "/master"),
		errorRes: map[string][]string {
			"exists": []string{".*branch.*already.*exists.*"},
		},
	}

	e.cmd.Dir = repoDir

	result, err := e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was a checking out a branch.")
	}

	if result == "exists" {
		e := &execHelper{
			cmd: exec.Command("git", "checkout", branchName),
			errorRes: map[string][]string {},
		}

		e.cmd.Dir = repoDir

		_, err := e.Run()

		if err != nil {
			return errors.Wrapf(err, "There was a problem checking out the branch.")
		}
	}

	// Add the remote repo where things will be pushed
	e = &execHelper{
		cmd: exec.Command("git", "remote", "add", forkName, fork),
		errorRes: map[string][]string {
			"exists": {".*remote.*already.*exists.*"},
		},
	}

	e.cmd.Dir = repoDir

	_, err = e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was a problem adding the remote repo.")
	}
	return nil
}

// push commits and pushes all changes
func push( repoDir string, forkName string, branchName string, messagePath string) error {
	e := &execHelper{
		cmd: exec.Command("git", "commit", "-a", "-F", messagePath),
		errorRes: map[string][]string {
			"empty": {".*nothing to commit.*"},
		},
	}

	e.cmd.Dir = repoDir

	_, err := e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was an error commiting the changes.")
	}

	e = &execHelper{
		cmd: exec.Command("git", "push", forkName, branchName),
		errorRes: map[string][]string {},
	}

	e.cmd.Dir = repoDir

	_, err = e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was a problem pushing the changes.")
	}
	return nil
}

// pr creates a pull request
func pr( repoDir string, baseBranch, messagePath string) error {
	// TODO(jlewi): We might want to use gh here. gh is the new official CLI
	// https://github.com/cli/cli/blob/trunk/docs/gh-vs-hub.md. According to the FAQ
	// https://github.com/cli/cli/blob/trunk/docs/gh-vs-hub.md#should-i-use-gh-or-hub
	// hub might be better for scripting.
	// both are go so we could potentially link them in.
	e := &execHelper{
		cmd: exec.Command("hub", "pull-request", "-f", "-b", baseBranch, "-F", messagePath),
		errorRes: map[string][]string {
			"exists": {".*already exists.*"},
		},
	}

	e.cmd.Dir = repoDir

	_, err := e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was an error creating the pull request.")
	}
	
	return nil
}

func main() {
	rootCmd.Execute()
}
