package main

import (
	"context"
	"flag"
	"fmt"
	"github.com/ghodss/yaml"
	"github.com/go-logr/logr"
	"github.com/go-logr/zapr"
	"github.com/kubeflow/testing/go/cmd/cleanup/types"
	"github.com/spf13/cobra"
	"go.uber.org/zap"
	"io/ioutil"
	"k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/dynamic"
	_ "k8s.io/client-go/plugin/pkg/client/auth/gcp"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/client-go/util/homedir"
	"path/filepath"
	"time"
)

type ApplyOptions struct {
	Input string
}

type GenerateOptions struct {
	Output string
}

var (
	opts  = ApplyOptions{}
	gOpts = GenerateOptions{}

	rootCmd = &cobra.Command{}

	applyCmd = &cobra.Command{
		Use:   "apply",
		Short: "Apply the specified file",
		Run: func(cmd *cobra.Command, args []string) {
			apply()
		},
	}

	log logr.Logger
)

func init() {
	rootCmd.AddCommand(applyCmd)

	applyCmd.Flags().StringVarP(&opts.Input, "file", "f", "", "The input file to process")
	applyCmd.MarkFlagRequired("file")
}

func initLogger() {
	// TODO(jlewi): Make the verbosity level configurable.

	// Start with a production logger config.
	config := zap.NewProductionConfig()

	// TODO(jlewi): In development mode we should use the console encoder as opposed to json formatted logs.

	// Increment the logging level.
	// TODO(jlewi): Make this a flag.
	config.Level = zap.NewAtomicLevelAt(zap.DebugLevel)

	zapLog, err := config.Build()
	if err != nil {
		panic(fmt.Sprintf("Could not create zap instance (%v)?", err))
	}
	log = zapr.NewLogger(zapLog)

	zap.ReplaceGlobals(zapLog)
}

func deleteGroup(client dynamic.Interface, group types.Group) {
	deploymentRes := schema.GroupVersionResource{Group: group.Group, Version: group.Version, Resource: group.Resource}

	minAge, err := time.ParseDuration(group.MinAge)

	if err != nil {
		log.Error(err, "Could not parse MinAge as durage", "MinAge", group.MinAge)
		return
	}

	resApi := client.Resource(deploymentRes)

	minCreationTime := time.Now().Add(-1 * minAge)

	maxResults := 100
	resultsPage := ""

	for ;; {
		results, err := resApi.Namespace(group.Namespace).List(context.Background(), metav1.ListOptions{
			Limit: int64(maxResults),
			Continue: resultsPage})

		if err != nil {
			k8sError, ok := err.(*errors.StatusError)

			if ok {
				if k8sError.ErrStatus.Reason == "Expired" {
					resultsPage = k8sError.ErrStatus.ListMeta.Continue
					continue
				}
			}
			log.Error(err, "Could not list items")
			return
		}

		for _, r := range results.Items {
			if r.GetCreationTimestamp().After(minCreationTime) {
				log.Info("Item too young for deletion", "name", r.GetName(), "creationTimestamp", r.GetCreationTimestamp())
				continue
			}

			log.Info("Deleting Item", "name", r.GetName(), "creationTimestamp", r.GetCreationTimestamp())
			err := resApi.Namespace(group.Namespace).Delete(context.Background(), r.GetName(), metav1.DeleteOptions{})
			if err != nil {
				log.Error(err, "Error deleting item", "name", r.GetName())
			}
		}

		if results.GetContinue() == "" {
			return
		}
		resultsPage = results.GetContinue()
	}

	return
}

func apply() {
	initLogger()

	if opts.Input == "" {
		log.Error(fmt.Errorf("No input file supplied"), "Input file must be supplied")
		return
	}

	b, err := ioutil.ReadFile(opts.Input)

	if err != nil {
		log.Error(err, "Could not read file", "file", opts.Input)
		return
	}

	bulkDelete := &types.BulkDelete{}
	err = yaml.Unmarshal(b, bulkDelete)

	if err != nil {
		log.Error(err, "Could not unmarshal object of type BulkK8sDelete")
		return
	}

	var kubeconfig *string
	if home := homedir.HomeDir(); home != "" {
		kubeconfig = flag.String("kubeconfig", filepath.Join(home, ".kube", "config"), "(optional) absolute path to the kubeconfig file")
	} else {
		kubeconfig = flag.String("kubeconfig", "", "absolute path to the kubeconfig file")
	}
	flag.Parse()

	config, err := clientcmd.BuildConfigFromFlags("", *kubeconfig)
	if err != nil {
		panic(err)
	}
	client, err := dynamic.NewForConfig(config)
	if err != nil {
		panic(err)
	}

	for _, g := range bulkDelete.Spec.Groups {
		deleteGroup(client, g)
	}


}

func main() {
	rootCmd.Execute()
}
