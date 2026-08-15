package q2d

import (
	"bytes"
	"encoding/hex"
	"os"
	"strings"
	"testing"
)

const testSuite = "eddsa-jws-2026"

func signingKey(t *testing.T) PrivateKey {
	t.Helper()
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
	return key
}

func TestTheHeaderCarriesTwoMembersInTheProfileOrder(t *testing.T) {
	header, err := Serialize(protectedHeader(testSuite, "test-requester-1"))
	if err != nil {
		t.Fatalf("serialize: %v", err)
	}
	// key_id before suite, which is serialization.md §1's ordering and not the
	// order they are written in protectedHeader.
	want := `{"key_id":"test-requester-1","suite":"eddsa-jws-2026"}`
	if string(header) != want {
		t.Errorf("header = %s", header)
	}
}

func TestSigningIsDeterministicAndRoundTrips(t *testing.T) {
	key := signingKey(t)
	payload := []byte(`{"a":1}`)
	first, err := SignCompact(payload, key, testSuite, "test-requester-1")
	if err != nil {
		t.Fatalf("sign: %v", err)
	}
	second, _ := SignCompact(payload, key, testSuite, "test-requester-1")
	if first != second {
		t.Error("two signings of one payload differ")
	}
	got, err := VerifyCompact(first, key.PublicKey())
	if err != nil || !bytes.Equal(got, payload) {
		t.Errorf("round trip: %x, %v", got, err)
	}
}

func TestTheCompactFormIsThreeBase64URLSegments(t *testing.T) {
	compact, err := SignCompact([]byte("{}"), signingKey(t), testSuite, "test-requester-1")
	if err != nil {
		t.Fatalf("sign: %v", err)
	}
	parts := strings.Split(compact, ".")
	if len(parts) != 3 {
		t.Fatalf("%d segments", len(parts))
	}
	for _, part := range parts {
		if _, err := DecodeBase64URL(part); err != nil {
			t.Errorf("%q is not base64url: %v", part, err)
		}
	}
}

func TestAWrongSegmentCountIsRefused(t *testing.T) {
	key := signingKey(t)
	compact, _ := SignCompact([]byte("{}"), key, testSuite, "test-requester-1")
	parts := strings.Split(compact, ".")
	for _, broken := range []string{
		strings.ReplaceAll(compact, ".", ""), // one segment
		parts[0] + "." + parts[1],            // two
		compact + ".extra",                   // four
		"",
	} {
		if _, err := VerifyCompact(broken, key.PublicKey()); err == nil {
			t.Errorf("%q was accepted", broken)
		}
	}
}

func TestATamperedPayloadIsRefused(t *testing.T) {
	key := signingKey(t)
	compact, _ := SignCompact([]byte(`{"a":1}`), key, testSuite, "test-requester-1")
	header, _, signature, _ := compactSegments(compact)
	swapped := header + "." + EncodeBase64URL([]byte(`{"a":2}`)) + "." + signature
	if _, err := VerifyCompact(swapped, key.PublicKey()); err == nil {
		t.Error("accepted")
	}
}

func TestATamperedHeaderIsRefused(t *testing.T) {
	// The header is covered by the signature, which is the reason it can carry
	// the suite at all.
	key := signingKey(t)
	compact, _ := SignCompact([]byte("{}"), key, testSuite, "test-requester-1")
	_, payload, signature, _ := compactSegments(compact)
	other, _ := Serialize(protectedHeader(testSuite, "test-requester-2"))
	swapped := EncodeBase64URL(other) + "." + payload + "." + signature
	if _, err := VerifyCompact(swapped, key.PublicKey()); err == nil {
		t.Error("accepted")
	}
}
