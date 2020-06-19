// nomos-wait is a simple tool to wait until nomos has been sync'd to the current commit.
package main

import (
	"flag"
	"fmt"
	log "github.com/golang/glog"
	"os/exec"
	"strings"
	"time"
)

func parseStatus(result string) (string, string, error) {
	lines := strings.Split(result,"\n")
	for _, l := range lines {
		columns := strings.Fields(l)
		if len(columns) != 5 || columns[0] != "*" {
			continue
		}
		return columns[2], columns[3], nil
	}

	return "", "", fmt.Errorf("Failed to parse nomos status from:\n%v", result)
}

func main() {
	var context = flag.String("context", "kf-ci-v1", "Kubernetes context for nomos status")
	flag.Parse()

	gitOut, err := exec.Command("git", "rev-parse", "--short", "HEAD").Output()

	if err != nil {
		log.Fatalf("Failed to get git commit; %v", err)
	}

	commit := strings.TrimSpace(string(gitOut))

	fmt.Printf("Current commit: %v\n", commit)

	for ;; {
		out, err := exec.Command("nomos", "--contexts=" + *context, "status").Output()

		if err != nil {
			log.Fatal(err)
		}

		status, syncCommit, err := parseStatus(string(out))

		if err != nil {
			log.Fatalf("Could not parse nomos output; %v", out)
		}

		fmt.Printf("Nomos status: %v; commit: %v \n", status, syncCommit)

		if status == "SYNCED" && strings.HasPrefix(syncCommit, commit) {
			fmt.Printf("nomos synced to commit %v \n", commit)
			return
		}
		fmt.Printf("Waiting for sync to commit %v \n", commit)
		time.Sleep(10 * time.Second)
	}
}
