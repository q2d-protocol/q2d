package q2d

import (
	"os"
	"strings"
	"testing"
)

func referenceRegistry(t *testing.T) SuiteRegistry {
	t.Helper()
	raw, err := os.ReadFile("registry/suites.json")
	if err != nil {
		t.Fatalf("registry/suites.json: %v", err)
	}
	registry, err := LoadSuiteRegistry(raw)
	if err != nil {
		t.Fatalf("the reference registry loads: %v", err)
	}
	return registry
}

func TestTheReferenceRegistryCarriesTheMandatorySuite(t *testing.T) {
	entry, err := referenceRegistry(t).Resolve("eddsa-jws-2026")
	if err != nil {
		t.Fatalf("registered: %v", err)
	}
	if entry.Status != SuiteActive {
		t.Errorf("status = %q", entry.Status)
	}
	if !strings.Contains(entry.Algorithm, "Ed25519") {
		t.Errorf("algorithm = %q", entry.Algorithm)
	}
}

func TestStatusComesFromTheFile(t *testing.T) {
	// The acceptance for this issue: change the file, and behaviour changes
	// without touching code. A compiled-in table would pass every other test in
	// this file.
	registry, err := LoadSuiteRegistry([]byte(`{"suites":[{"id":"x","algorithm":"a",
		"serialization":"s","hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"deprecated"}]}`))
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	entry, _ := registry.Resolve("x")
	if entry.Status.MayProduce() {
		t.Error("a deprecated suite may not produce")
	}
	if !entry.Status.MayVerify() {
		t.Error("a deprecated suite must still verify")
	}
}

func TestTheThreeStatusesDifferInTheWaySection6Says(t *testing.T) {
	for _, c := range []struct {
		status          SuiteStatus
		produce, verify bool
	}{
		{SuiteActive, true, true},
		// Deprecated is the asymmetric one, and the asymmetry is the point.
		{SuiteDeprecated, false, true},
		{SuiteWithdrawn, false, false},
	} {
		if c.status.MayProduce() != c.produce || c.status.MayVerify() != c.verify {
			t.Errorf("%s: produce=%v verify=%v", c.status,
				c.status.MayProduce(), c.status.MayVerify())
		}
	}
}

func TestARegistryThatMustNotLoad(t *testing.T) {
	for name, document := range map[string]string{
		// Fail-closed: not a default, and not ignored. A registry this build
		// cannot read the rules of is one it must not act on.
		"unknown status": `{"suites":[{"id":"x","algorithm":"a","serialization":"s",
			"hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"provisional"}]}`,
		"duplicate identifier": `{"suites":[
			{"id":"x","algorithm":"a","serialization":"s","hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"active"},
			{"id":"x","algorithm":"a","serialization":"s","hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"withdrawn"}]}`,
		// Because this reads with Parse rather than encoding/json. Last-wins
		// would let the second copy decide what a verifier accepts.
		"duplicate key": `{"suites":[{"id":"x","algorithm":"a","serialization":"s",
			"hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"withdrawn","status":"active"}]}`,
		// A registry with no entries verifies nothing, so loading one silently
		// would turn a distribution failure into a total outage with no error.
		"no entries":          `{"suites":[]}`,
		"no suites":           `{"registry_id":"x"}`,
		"suites not an array": `{"suites":{"id":"x"}}`,
		"missing status":      `{"suites":[{"id":"x","algorithm":"a","serialization":"s","hash":"h"}]}`,
		"missing id":          `{"suites":[{"algorithm":"a","serialization":"s","hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"active"}]}`,
		"status not a string": `{"suites":[{"id":"x","algorithm":"a","serialization":"s",
			"hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":1}]}`,
	} {
		if _, err := LoadSuiteRegistry([]byte(document)); err == nil {
			t.Errorf("%s: loaded", name)
		}
	}
}

func TestAnUnregisteredSuiteDoesNotResolve(t *testing.T) {
	_, err := referenceRegistry(t).Resolve("hmac-sha1-1999")
	if err == nil {
		t.Fatal("resolved")
	}
	// The identifier is echoed — it came from the sender. What must not appear
	// is any other suite's name.
	if !strings.Contains(err.Error(), "hmac-sha1-1999") {
		t.Errorf("message does not name the identifier: %v", err)
	}
	if strings.Contains(err.Error(), "eddsa") {
		t.Errorf("message names a registered suite: %v", err)
	}
}

func TestAPinnedDigestMustMatch(t *testing.T) {
	raw := []byte(`{"suites":[{"id":"x","algorithm":"a","serialization":"s",
		"hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"active"}]}`)
	digest := Digest(raw)
	if _, err := LoadPinnedSuiteRegistry(raw, digest); err != nil {
		t.Fatalf("the matching digest was refused: %v", err)
	}

	wrong := "sha256:0000000000000000000000000000000000000000000000000000000000000000"
	_, err := LoadPinnedSuiteRegistry(raw, wrong)
	if err == nil {
		t.Fatal("a mismatched digest loaded")
	}
	if !strings.Contains(err.Error(), digest) || !strings.Contains(err.Error(), wrong) {
		t.Errorf("the message needs both digests to be actionable: %v", err)
	}
}

func TestTheDigestIsCheckedBeforeTheBytesAreParsed(t *testing.T) {
	// Bytes that are not JSON at all. If the digest were checked second, this
	// would fail with a parse error — telling an operator that a file they never
	// pinned is malformed, which is a fact about attacker input and not about
	// their configuration.
	_, err := LoadPinnedSuiteRegistry([]byte("not json"), "sha256:whatever")
	if err == nil {
		t.Fatal("loaded")
	}
	if !strings.Contains(err.Error(), "pinned") || strings.Contains(err.Error(), "parse") {
		t.Errorf("the digest was not what refused it: %v", err)
	}
}
