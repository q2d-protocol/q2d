package q2d

import (
	"fmt"
	"strings"
	"testing"
)

func policyRegistry(t *testing.T, status string) SuiteRegistry {
	t.Helper()
	document := fmt.Sprintf(`{"suites":[
		{"id":"eddsa-jws-2026","algorithm":"a","serialization":"s","hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"%s"},
		{"id":"withdrawn-suite","algorithm":"a","serialization":"s","hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"withdrawn"}]}`,
		status)
	registry, err := LoadSuiteRegistry([]byte(document))
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	return registry
}

func TestTheDefaultIsTheMandatorySuiteAlone(t *testing.T) {
	policy, err := NewSuitePolicy(policyRegistry(t, "active"), nil)
	if err != nil {
		t.Fatalf("default policy: %v", err)
	}
	if !policy.Accepts(DefaultAcceptable) {
		t.Error("the default does not accept the mandatory suite")
	}
	if got := policy.Advertised(); len(got) != 1 || got[0] != DefaultAcceptable {
		t.Errorf("advertised = %v", got)
	}
}

func TestConfigurationMayRaiseTheFloor(t *testing.T) {
	// Naming fewer suites than the floor admits is the direction that is always
	// allowed.
	policy, err := NewSuitePolicy(policyRegistry(t, "active"), []string{"eddsa-jws-2026"})
	if err != nil {
		t.Fatalf("policy: %v", err)
	}
	if !policy.Accepts("eddsa-jws-2026") || policy.Accepts("withdrawn-suite") {
		t.Error("the configured set is not what was configured")
	}
}

func TestConfigurationMayNotLowerItAndStartupFails(t *testing.T) {
	// The important half. Not clamped, not warned about, not dropped: a clamped
	// misconfiguration reads as success.
	_, err := NewSuitePolicy(policyRegistry(t, "active"), []string{"withdrawn-suite"})
	if err == nil {
		t.Fatal("a withdrawn suite was accepted into the policy")
	}
	if !strings.Contains(err.Error(), "withdrawn-suite") || !strings.Contains(err.Error(), "floor") {
		t.Errorf("the message is not actionable: %v", err)
	}
}

func TestAnUnregisteredSuiteIsBelowTheFloor(t *testing.T) {
	if _, err := NewSuitePolicy(policyRegistry(t, "active"), []string{"hmac-sha1-1999"}); err == nil {
		t.Error("accepted")
	}
}

func TestADeprecatedSuiteMayStillBeAccepted(t *testing.T) {
	// §6's asymmetry reaches the policy: receipts signed under a deprecated
	// suite remain evidence, so a verifier may keep accepting it.
	policy, err := NewSuitePolicy(policyRegistry(t, "deprecated"), nil)
	if err != nil {
		t.Fatalf("policy: %v", err)
	}
	if !policy.Accepts("eddsa-jws-2026") {
		t.Error("a deprecated suite must still verify")
	}
}

func TestAWithdrawnDefaultFailsStartup(t *testing.T) {
	// The default names the MTI suite; if the registry says it is withdrawn,
	// this build cannot verify anything and says so at startup rather than
	// rejecting every message at run time with a reason nobody connects to the
	// registry.
	_, err := NewSuitePolicy(policyRegistry(t, "withdrawn"), nil)
	if err == nil {
		t.Fatal("started")
	}
	if !strings.Contains(err.Error(), "eddsa-jws-2026") {
		t.Errorf("the message does not name the suite: %v", err)
	}
}

func TestARegisteredSuiteThisBuildCannotExecuteIsBelowTheFloor(t *testing.T) {
	// The floor is not "the registry said so". A registry is data, and one naming
	// a suite this code cannot execute would otherwise be accepted into the
	// policy — after which SignCompact produces Ed25519 under that suite's
	// identifier.
	registry, err := LoadSuiteRegistry([]byte(`{"suites":[{"id":"pqc-dilithium-2030",
		"algorithm":"a","serialization":"s","hash":"h","effective_from":"2030-01-01",
		"deprecated_from":null,"withdrawn_from":null,"security_notes":[],
		"references":[],"status":"active"}]}`))
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if _, err := registry.Resolve("pqc-dilithium-2030"); err != nil {
		t.Fatalf("registered: %v", err)
	}
	if _, err := NewSuitePolicy(registry, []string{"pqc-dilithium-2030"}); err == nil {
		t.Error("a suite this build cannot execute was accepted")
	}
}

func TestTheImplementedSetCannotBeChangedByACaller(t *testing.T) {
	// An exported mutable slice would let a caller append an identifier it read
	// out of a registry, after which this build treats an unimplemented suite as
	// implemented — the guard removing itself. Rust states the set as a const, so
	// what a caller can do to it must match.
	got := ImplementedSuites()
	got[0] = "anything-at-all"
	if !implementsSuite("eddsa-jws-2026") || implementsSuite("anything-at-all") {
		t.Error("mutating the returned slice changed what this build implements")
	}
}
