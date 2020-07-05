package main

import (
	"github.com/onrik/logrus/filename"
	"github.com/pkg/errors"
	log "github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"os"
	"os/exec"
	"regexp"
)

type cliOptions struct {
	upstreamName string
	repoDir      string
	forkName     string
	fork         string
	branchName   string
	messagePath  string
	baseBranch   string
	refSpec string
	jsonLogFormat bool
}

var (
	options = cliOptions{}

	rootCmd = &cobra.Command{
		Use:   "prctl",
		Short: "A CLI to help with creating PRs",
		Long:  `prctl is a CLI to help create PRs as part of GitOps workflows`,
	}

	branchCmd = &cobra.Command{
		Use:   "branch",
		Short: "Create a branch to be used for creating PRs.",
		Long:  `prctl branch creates a branch on a remote repo to contain any changes`,
		Run: func(cmd *cobra.Command, args []string) {
			if err := setup(); err != nil {
				log.Fatalf("Failed to setup the app; error: %+v", err)
				return
			}
			err := branch(options.repoDir, options.upstreamName, options.forkName, options.fork, options.branchName)

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
			if err := setup(); err != nil {
				log.Fatalf("Failed to setup the app; error: %+v", err)
				return
			}
			err := push(options.repoDir, options.forkName, options.refSpec, options.messagePath)

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
			if err := setup(); err != nil {
				log.Fatalf("Failed to setup the app; error: %+v", err)
				return
			}
			err := pr(options.repoDir, options.baseBranch, options.messagePath)

			if err != nil {
				log.Fatalf("push failed; error: %+v", err)
			}
		},
	}

	// Create a map of ids for various git errors to regexes matching the output
	gitErrorRegexes = map[string][]string{
		NothingToCommit:     {".*nothing to commit.*"},
		UnshallowOnComplete: {".*unshallow on a complete repository.*"},
		BranchExists:        {".*branch.*already.*exists.*"},
		RemoteExists:        {".*remote.*already.*exists.*"},
	}
)

const (
	// Define constants for the various known errors
	NothingToCommit     = "nothingToCommit"
	UnshallowOnComplete = "unshallowOnComplete"
	BranchExists        = "branchExists"
	RemoteExists        = "remoteExists"
)

// setup performs common app setup
func setup() error {
	if options.jsonLogFormat {
		log.SetFormatter(&log.JSONFormatter{})
	}
	return nil
}

func init() {
	rootCmd.AddCommand(branchCmd)
	rootCmd.AddCommand(pushCmd)
	rootCmd.AddCommand(prCmd)

	rootCmd.PersistentFlags().BoolVar(&options.jsonLogFormat, "json-logs", false, "Use json formatted log enteries")

	branchCmd.Flags().StringVarP(&options.upstreamName, "upstreamName", "", "origin", "The name of the remote repository corresponding to the upstream URL")
	branchCmd.Flags().StringVarP(&options.repoDir, "repoDir", "", "", "Directory where the code is checked out")
	branchCmd.Flags().StringVarP(&options.forkName, "forkName", "", "", "Name to assign the remote repo for the fork")
	branchCmd.Flags().StringVarP(&options.fork, "fork", "", "", "Name to assign the remote repo for the fork")
	branchCmd.Flags().StringVarP(&options.branchName, "branchName", "", "", "Name to the branch to create")

	branchCmd.MarkFlagRequired("forkName")
	branchCmd.MarkFlagRequired("fork")
	branchCmd.MarkFlagRequired("branchName")

	pushCmd.Flags().StringVarP(&options.repoDir, "repoDir", "", "", "Directory where the code is checked out")
	pushCmd.Flags().StringVarP(&options.forkName, "forkName", "", "", "Name to assign the remote repo for the fork")
	pushCmd.Flags().StringVarP(&options.refSpec, "refSpec", "", "", "The refSpec to use for the push")
	pushCmd.Flags().StringVarP(&options.messagePath, "messagePath", "", "", "Path to a file containing the message to use for the commit")

	pushCmd.MarkFlagRequired("refSpec")
	pushCmd.MarkFlagRequired("forkName")
	pushCmd.MarkFlagRequired("messagePath")

	prCmd.Flags().StringVarP(&options.repoDir, "repoDir", "", "", "Directory where the code is checked out")
	prCmd.Flags().StringVarP(&options.baseBranch, "baseBranch", "", "kubeflow:master", "Name of the branch to use as the base")
	prCmd.Flags().StringVarP(&options.messagePath, "messagePath", "", "", "Path to a file containing the message to use for the commit")

	prCmd.MarkFlagRequired("baseBranch")
	prCmd.MarkFlagRequired("messagePath")

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

// matchRePatterns checks if the string matches one of the supplied patterns
// Returns the id of the error that matched if any; the empty string otherwise.
// error non nil if an unmatched exception occur.
func matchRePatterns(patterns map[string][]string, s string) (string, error) {
	for eid, p := range patterns {
		for _, re := range p {
			match, err := regexp.MatchString(re, s)

			if err != nil {
				return "", errors.WithStack(err)
			}

			if match {
				return eid, nil
			}
		}
	}
	return "", nil
}

// Run executes the command stored in the execHelper
// Returns the id of the error that matched if any; the empty string otherwise.
// error non nil if an unmatched exception occur.
func (e *execHelper) Run() (string, error) {
	log.Infof("Executing command: %v", e.cmd.String())
	out, err := e.cmd.CombinedOutput()

	// It looks like out is sometimes set even if there is an error.
	log.Infof("Output of %v;\n%v", e.cmd.String(), string(out))
	if err != nil {
		m, err := matchRePatterns(e.errorRes, string(out))

		if err != nil {
			log.Errorf("Error trying to match output against known regexes; Error %v", err)
			return "", err
		}
		if m != "" {
			return m, nil
		} else {
			return "", err
		}
	}

	return "", nil
}

// branch creates a branch for all the changes
func branch(repoDir string, upstreamName string, forkName string, forkUrl string, branchName string) error {
	if repoDir == "" {
		repoDir, err := os.Getwd()
		if err != nil {
			return errors.WithStack(errors.Errorf("repoDir not provided and couldn't get current directory; Error: %v", err))
		}
		log.Infof("Using current directory; %v", repoDir)
	}

	e := &execHelper{
		cmd:      exec.Command("git", "fetch", "--unshallow"),
		errorRes: gitErrorRegexes,
	}

	e.cmd.Dir = repoDir

	_, err := e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was a problem unshallowing the repo.")
	}

	// Create a new branch for the pull request.
	e = &execHelper{
		cmd:      exec.Command("git", "checkout", "-b", branchName, upstreamName+"/master"),
		errorRes: gitErrorRegexes,
	}

	e.cmd.Dir = repoDir

	result, err := e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was a problem checking out the branch.")
	}

	if result == BranchExists {
		e := &execHelper{
			cmd:      exec.Command("git", "checkout", branchName),
			errorRes: gitErrorRegexes,
		}

		e.cmd.Dir = repoDir

		_, err := e.Run()

		if err != nil {
			return errors.Wrapf(err, "There was a problem checking out the branch.")
		}
	}

	// Add the remote repo where things will be pushed
	e = &execHelper{
		cmd:      exec.Command("git", "remote", "add", forkName, forkUrl),
		errorRes: gitErrorRegexes,
	}

	e.cmd.Dir = repoDir

	_, err = e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was a problem adding the remote repo.")
	}
	return nil
}

// push commits and pushes all changes
func push(repoDir string, forkName string, refSpec string, messagePath string) error {
	if refSpec == "" {
		return errors.WithStack(errors.Errorf("refSpec can't be empty"))
	}

	if forkName == "" {
		return errors.WithStack(errors.Errorf("forkName can't be empty"))
	}

	if messagePath == "" {
		return errors.WithStack(errors.Errorf("messagePath can't be empty"))
	}

	if repoDir == "" {
		repoDir, err := os.Getwd()
		if err != nil {
			return errors.WithStack(errors.Errorf("repoDir not provided and couldn't get current directory; Error: %v", err))
		}
		log.Infof("Using current directory; %v", repoDir)
	}

	e := &execHelper{
		cmd:      exec.Command("git", "add", "--all"),
		errorRes: gitErrorRegexes,
	}

	e.cmd.Dir = repoDir

	_, err := e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was an error staging allchanges.")
	}


	e = &execHelper{
		cmd:      exec.Command("git", "commit", "-a", "-F", messagePath),
		errorRes: gitErrorRegexes,
	}

	e.cmd.Dir = repoDir

	_, err = e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was an error commiting the changes.")
	}

	e = &execHelper{
		// -f is needed because its possible the branch already exists; e.g. because we previously
		// attempted to create PR but then closed it say because the PR became outdated.
		// Furthermore, we can reuse the same branch for multiple updates.
		cmd:      exec.Command("git", "push", "-f", forkName, refSpec),
		errorRes: map[string][]string{},
	}

	e.cmd.Dir = repoDir

	_, err = e.Run()

	if err != nil {
		return errors.Wrapf(err, "There was a problem pushing the changes.")
	}
	return nil
}

// pr creates a pull request
func pr(repoDir string, baseBranch, messagePath string) error {
	if repoDir == "" {
		repoDir, err := os.Getwd()
		if err != nil {
			return errors.WithStack(errors.Errorf("repoDir not provided and couldn't get current directory; Error: %v", err))
		}
		log.Infof("Using current directory; %v", repoDir)
	}

	// TODO(jlewi): We might want to use gh here. gh is the new official CLI
	// https://github.com/cli/cli/blob/trunk/docs/gh-vs-hub.md. According to the FAQ
	// https://github.com/cli/cli/blob/trunk/docs/gh-vs-hub.md#should-i-use-gh-or-hub
	// hub might be better for scripting.
	// both are go so we could potentially link them in.
	e := &execHelper{
		cmd: exec.Command("hub", "pull-request", "-f", "-b", baseBranch, "-F", messagePath),
		errorRes: map[string][]string{
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
