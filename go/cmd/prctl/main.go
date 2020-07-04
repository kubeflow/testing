package main

import (
	"encoding/json"
	"fmt"
	"github.com/bradleyfalzon/ghinstallation"
	"github.com/cli/cli/api"
	"github.com/kubeflow/testing/go/pkg/ghrepo"
	"github.com/onrik/logrus/filename"
	"github.com/pkg/errors"
	log "github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"io/ioutil"
	"net/http"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
)

type cliOptions struct {
	upstreamName  string
	repoDir       string
	repo          string
	forkName      string
	fork          string
	branchName    string
	messagePath   string
	baseBranch    string
	refSpec       string
	jsonLogFormat bool
	privateKey    string
	installId     string
	appId         string
	forkRef       string
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
			err := pr(options.repo, options.baseBranch, options.forkRef, options.messagePath)

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

	prCmd.Flags().StringVarP(&options.repo, "repo", "", "", "The repo to create the PR in in the form OWNER/REPO")
	prCmd.Flags().StringVarP(&options.baseBranch, "baseBranch", "", "master", "Name of the branch to merge your changes into")
	prCmd.Flags().StringVarP(&options.forkRef, "forkRef", "", "", "Reference to the branch to create the PR from; typically ${user}:${branch}")
	prCmd.Flags().StringVarP(&options.messagePath, "messagePath", "", "", "Path to a file containing the message to use for the commit")
	prCmd.Flags().StringVarP(&options.appId, "appId", "", "", "App id for the GitHub app")
	prCmd.Flags().StringVarP(&options.privateKey, "privateKey", "", "", "Path to the file containing the private key for the GitHub app")

	prCmd.MarkFlagRequired("baseBranch")
	prCmd.MarkFlagRequired("forkRef")
	prCmd.MarkFlagRequired("messagePath")
	prCmd.MarkFlagRequired("privateKey")
	prCmd.MarkFlagRequired("appId")

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

func getInstallId(appId int64, privateKey string, owner string, repo string) (int64, error) {
	tr := http.DefaultTransport

	appTr, err := ghinstallation.NewAppsTransportKeyFromFile(tr, appId, privateKey)

	client := &http.Client{Transport: appTr}

	if err != nil {
		return 0, errors.WithStack(errors.Wrapf(err, "There was a problem getting the GitHub installation id"))
	}

	// Get the installtion id
	url := fmt.Sprintf("https://api.github.com/repos/%v/%v/installation", owner, repo)
	resp, err := client.Get(url)

	if err != nil {
		return 0, errors.WithStack(errors.Wrapf(err, "There was a problem getting the GitHub installation id"))
	}

	if resp.StatusCode != http.StatusOK {
		// TODO(jlewi): Should we try to read the body and include that in the error message?
		return 0, errors.WithStack(errors.Wrapf(err, "There was a problem getting the GitHub installation id; Get %v returned statusCode %v; Response:\n%+v", url, resp.StatusCode, resp))
	}

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return 0, errors.WithStack(errors.Wrapf(err, "There was a problem reading the response body."))
	}

	type idResponse struct {
		Id int64 `json:"id"`
	}

	r := &idResponse{}
	err = json.Unmarshal(body, r)

	if err != nil {
		return 0, errors.WithStack(errors.Wrapf(err, "Could not unmarshal json:\n %v", body))
	}
	return r.Id, nil
}

// pr creates a pull request
// repoDir the directory of your repository.
// baseBranch the branch into which your code should be merged.
//
// TODO(jlewi): We should be able to determine forkRef automatically from the local information in the repo.
// On the other hand would it be better to not
func pr(repo string, baseBranch, forkRef, messagePath string) error {
	if repo == "" {
		return errors.WithStack(errors.Errorf("repo must be provided in the form OWNER/REPO"))
	}

	appId, err := strconv.ParseInt(options.appId, 10, 64)

	if err != nil {
		return errors.WithStack(errors.Errorf("Could not convert appId %v to integer; error: %v", options.appId, err))
	}

	baseRepo, err := ghrepo.FromFullName(repo)

	if err != nil {
		return errors.WithStack(errors.Wrapf(err, "There was a problem getting the base repo."))
	}

	log.Infof("Base repository: %v/%v", baseRepo.RepoOwner(), baseRepo.RepoName())

	// Shared transport to reuse TCP connections.
	tr := http.DefaultTransport

	installId, err := getInstallId(appId, options.privateKey, baseRepo.RepoOwner(), baseRepo.RepoName())

	if err != nil {
		return errors.WithStack(errors.Wrapf(err, "There was a problem getting the GitHub installation id"))
	}

	if installId == 0 {
		return errors.WithStack(errors.Errorf("Could not obtain a GitHub installId for AppId %v on repo %v/%v; Is the app installed?", appId, baseRepo.RepoOwner(), baseRepo.RepoName()))
	}

	log.Infof("Repo %v/%v install id: %v", baseRepo.RepoOwner(), baseRepo.RepoName(), installId)

	if err != nil {
		return errors.WithStack(errors.Wrapf(err, "Could not obtain a GitHub installId for AppId %v on repo %v/%v; Is the app installed?", appId, baseRepo.RepoOwner(), baseRepo.RepoName()))
	}

	// Wrap the shared transport for use with the app ID 1 authenticating with installation ID 99.
	itr, err := ghinstallation.NewKeyFromFile(tr, appId, installId, options.privateKey)

	if err != nil {
		return errors.WithStack(errors.Wrapf(err, "Error creating githubinstallation"))
	}

	client := api.NewClient(api.ReplaceTripper(itr))

	// TODO(jlewi): Fill in with actual values by readin
	messageBytes, err := ioutil.ReadFile(messagePath)

	if err != nil {
		return errors.WithStack(errors.Wrapf(err, "There was an error reading file: %v", messagePath))
	}

	lines := strings.SplitN(string(messageBytes), "\n", 2)

	title := ""
	body := ""

	if len(lines) >= 1 {
		title = lines[0]
	}

	if len(lines) >= 2 {
		body = lines[1]
	}

	// For more info see:
	// https://developer.github.com/v4/input_object/createpullrequestinput/
	//
	// body ad title can't be blank.
	params := map[string]interface{}{
		"title": title,
		"body":  body,
		"draft": false,
		// The name of the branch to merge changes into.
		"baseRefName": baseBranch,
		// The name of the reference to merge changes from; typically in the form $user:$branch
		"headRefName": forkRef,
	}

	// Forkref will either be OWNER:BRANCH when a different repository is used as the fork.
	// Or it will be just BRANCH when merging from a branch in the same repo as repo
	pieces := strings.Split(forkRef, ":")

	forkOwner := baseRepo.RepoOwner()
	forkBranch := ""
	if len(pieces) == 1 {
		forkBranch = pieces[0]
	} else {
		forkOwner = pieces[0]
		forkBranch = pieces[1]
	}

	// Query the GitHub API to get actual repository info.
	baseRepository, err := api.GitHubRepo(client, baseRepo)

	if err != nil {
		return errors.WithStack(errors.Wrapf(err, "There was an error getting repository information."))
	}
	pr, err := api.CreatePullRequest(client, baseRepository, params)
	if err != nil {
		graphErr, ok := err.(*api.GraphQLErrorResponse)
		if ok {
			for _, gErr := range graphErr.Errors {
				if isMatch, _ := regexp.MatchString("A pull request already exists.*", gErr.Message); isMatch {
					// TODO(jlewi): Might be useful to find and print out the URL of the existing PR
					log.Info(gErr.Message)

					// If the fork is in a different repo then the head reference is OWNER:BRANCH
					// If we are creating the PR from a different branch in the same repo as where we are creating
					// the PR then we just use BRANCH as the ref
					headBranchRef := forkRef

					if forkOwner == baseRepo.RepoOwner() {
						headBranchRef = forkBranch
					}

					existingPR, err := api.PullRequestForBranch(client, baseRepo, baseBranch, headBranchRef)
					var notFound *api.NotFoundError
					if err != nil && errors.As(err, &notFound) {
						return fmt.Errorf("error checking for existing pull request: %w", err)
					}

					log.Infof("A pull request for branch %q into branch %q already exists:\n%s", forkRef, baseBranch, existingPR.URL)

					return nil
				}
			}
		}

		return errors.WithStack(errors.Wrapf(err, "Failed to create pull request"))
	}

	log.Infof("Created PR: %+v", pr.URL)
	return nil
}

func main() {
	rootCmd.Execute()
}
