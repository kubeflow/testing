package tests

import "testing"

// TestValidateConfig runs some validation tests.
// Sole purpose of this test is to verify that in presubmits we can use
// Tekton to trigger the workflow to run go unittests
func TestValidateConfig(t *testing.T) {
	t.Log("Success.")
}
