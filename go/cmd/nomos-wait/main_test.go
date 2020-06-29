package main

import "testing"

func TestParse(t *testing.T) {
	testData := `Current   Context    Status           Last Synced Token   Sync Branch
-------   -------    ------           -----------------   -----------
*         kf-ci-v1   SYNCED           79629ca7            gcp_blueprints`

	status, commit, err := parseStatus(testData)
	//#err := parseS(testData)

	if err != nil {
		t.Errorf("Expected nil; got error %v", err)
	}

	expected := "79629ca7"
	if commit != expected {
		t.Errorf("Got commit: %v; want %v", commit, expected)
	}

	expectedStatus := "SYNCED"
	if status != expectedStatus {
		t.Errorf("Got status: %v; want %v", commit, expectedStatus)
	}
}
