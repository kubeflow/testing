package types

import metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

const (
	BulkDeleteKind = "BulkDelete"
)

// BulkK8sDelete delete all of the K8s objects of a given kind in a namespace
type BulkDelete struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec BulkDeleteSpec `json:"spec,omitempty"`
}

type BulkDeleteSpec struct {
	Groups []Group `json:"groups,omitempty"`
}

type Group struct {
	Namespace string        `json:"namespace,omitempty"`
	Resource string        `json:"resource,omitempty"`
	Group string        `json:"group,omitempty"`
	Version string    `json:"version,omitempty"`
	// MinAge is the minimum age of an item to be eligible for deletion
	MinAge string `json:"minAge,omitempty"`
}

