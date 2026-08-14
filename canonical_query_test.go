package q2d

import (
	"os"
	"testing"
)

// canonicalQuery is tools/author_message.py's QUERY: every field
// core-model.md §2 marks required, and no optional one, so the bytes are the
// smallest a conforming requester produces.
//
// Built by hand rather than read from testdata/canonical-query.json, because
// parsing is P-002 issue 4 and does not exist yet. When it does, this becomes a
// round trip and the hand-built copy goes.
func canonicalQuery() Value {
	return Object{
		"q2d_version": String("0.1"),
		"type":        String("query"),
		"query_id":    String("urn:uuid:0e183389-0f37-4c5f-8c56-1ea7e5818e18"),
		"issued_at":   String("2026-07-31T09:00:00Z"),
		"expires_at":  String("2026-07-31T09:05:00Z"),
		"nonce":       String("Ux7kFQ2mS0aVvJ1cPzN4bw"),
		"requester": Object{
			"principal": String("did:key:z6MkRequesterPrincipal"),
			"agent":     String("did:key:z6MkRequesterAgent"),
			"delegation": Object{
				"profile": String("local-pairing-0.1"), "reference": String("sha256:7ef1")},
		},
		"target": Object{"custodian": String("https://friend.example/.well-known/q2d")},
		"predicate": Object{
			"id":              String("https://q2d.dev/predicates/dietary/menu-compatible"),
			"version":         String("0.1"),
			"registry_digest": String("sha256:bd08ff230de0d8ce34de99967f7a9097988b49058f0a21dd35b9444c24098e35"),
			"public_context": Object{"menu": Array{
				Object{"item_id": String("risotto"), "contains": Array{String("milk")}},
				Object{"item_id": String("salad"), "contains": Array{}},
			}},
		},
		"answer_contract": Object{
			"release_shape":         String("boolean"),
			"domain":                Array{Bool(false), Bool(true)},
			"allowed_detail_fields": Array{},
		},
		"purpose": Object{
			"code":        String("social.meal-planning"),
			"description": String("Choose a dinner venue for 2026-07-31")},
		"delivery": Object{
			"answer_recipient": String("did:key:z6MkRequesterRuntime"),
			"permitted_sinks":  Array{String("urn:q2d:sink:model:local")}},
		"signature": Object{
			"profile": String("eddsa-jws-2026"), "key_id": String("test-requester-1")},
	}
}

// TestCanonicalQuerySerializesToTheFixtureBytes is P-002 §7's first acceptance
// criterion from the Go side. testdata/README.md describes the fixture and the
// two sibling tests.
func TestCanonicalQuerySerializesToTheFixtureBytes(t *testing.T) {
	expected, err := os.ReadFile("testdata/canonical-query.serialized")
	if err != nil {
		t.Fatalf("cannot read the fixture: %v", err)
	}
	// Compared as text on failure: a byte-count mismatch tells a reader
	// nothing, and the profile emits UTF-8 by construction.
	if got, want := text(t, canonicalQuery()), string(expected); got != want {
		t.Errorf("serialized query differs from the fixture\n got: %s\nwant: %s", got, want)
	}
}

func TestCanonicalQuerySignatureBlockCarriesNoValue(t *testing.T) {
	// E-31: under eddsa-jws-2026 the signature is the compact form's third
	// segment, so a payload carrying signature.value would be signing itself.
	serialized := text(t, canonicalQuery())
	if !contains(serialized, `"signature":{"key_id"`) {
		t.Error("the signature block is not where the profile puts it")
	}
	if contains(serialized, `"value"`) {
		t.Error("the payload carries a signature value")
	}
}

func contains(haystack, needle string) bool {
	return len(haystack) >= len(needle) && indexOf(haystack, needle) >= 0
}

func indexOf(haystack, needle string) int {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return i
		}
	}
	return -1
}
