package q2d

import (
	"encoding/hex"
	"os"
	"strings"
	"testing"
)

// Signing the canonical query reproduces the committed compact string.
//
// P-003 issue 5's acceptance, in the strongest form available today.
//
// testdata/canonical-query.signed is what tools/author_vectors.py produces from
// testdata/canonical-query.json, and it is byte-identical to
// message/sign/query-minimal's expected output — a Python test asserts that, so
// the fixture and the corpus cannot drift apart. This test and
// tests/canonical_query_signed.rs are the other two readings.
//
// Why not read the vector file directly: a corpus vector is not a Q2D structure.
// It carries a signed string of 1604 bytes, and Parse applies core-model.md
// §2.8's 2 KiB protocol-string limit, which is a rule about messages. Reading a
// vector needs the runner's own parser, which is cmd/q2d-conform's and
// deliberately separate.
func TestSigningTheCanonicalQueryReproducesTheCommittedString(t *testing.T) {
	raw, err := os.ReadFile("testdata/canonical-query.json")
	if err != nil {
		t.Fatalf("the canonical query: %v", err)
	}
	query, err := Parse(raw)
	if err != nil {
		t.Fatalf("the canonical query parses: %v", err)
	}

	material, err := os.ReadFile("conformance/keys/ed25519-test-only.json")
	if err != nil {
		t.Fatalf("key material: %v", err)
	}
	document, err := Parse(material)
	if err != nil {
		t.Fatalf("key material parses: %v", err)
	}
	seedText := string(document.(Object)["keys"].(Object)["test-requester-1"].(Object)["seed"].(String))
	seed, err := hex.DecodeString(seedText)
	if err != nil {
		t.Fatalf("seed: %v", err)
	}
	key, err := NewPrivateKey(seed)
	if err != nil {
		t.Fatalf("key: %v", err)
	}

	payload, err := Serialize(query)
	if err != nil {
		t.Fatalf("the query serializes: %v", err)
	}
	produced, err := SignCompact(payload, key, "eddsa-jws-2026", "test-requester-1")
	if err != nil {
		t.Fatalf("signing: %v", err)
	}

	expected, err := os.ReadFile("testdata/canonical-query.signed")
	if err != nil {
		t.Fatalf("testdata/canonical-query.signed: %v", err)
	}
	if produced != strings.TrimRight(string(expected), "\n") {
		t.Errorf("produced a different compact string:\n%s", produced)
	}
}
