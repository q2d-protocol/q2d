package q2d

import (
	"encoding/hex"
	"os"
	"strings"
	"testing"
)

func verifyRegistry(t *testing.T) SuiteRegistry {
	t.Helper()
	return referenceRegistry(t)
}

func keyFor(t *testing.T, keyID string) PrivateKey {
	t.Helper()
	material, err := os.ReadFile("conformance/keys/ed25519-test-only.json")
	if err != nil {
		t.Fatalf("key material: %v", err)
	}
	document, err := Parse(material)
	if err != nil {
		t.Fatalf("key material parses: %v", err)
	}
	text := string(document.(Object)["keys"].(Object)[keyID].(Object)["seed"].(String))
	seed, err := hex.DecodeString(text)
	if err != nil {
		t.Fatalf("seed: %v", err)
	}
	key, err := NewPrivateKey(seed)
	if err != nil {
		t.Fatalf("key: %v", err)
	}
	return key
}

func verifyResolver(t *testing.T) KeyResolver {
	t.Helper()
	keys := NewFixedKeys()
	for _, id := range []string{"test-requester-1", "test-requester-2", "test-custodian-1"} {
		if err := keys.Add(id, keyFor(t, id).PublicKey().Bytes()); err != nil {
			t.Fatalf("%s: %v", id, err)
		}
	}
	return keys
}

// canonicalSigned is the same string the corpus asserts.
func canonicalSigned(t *testing.T) string {
	t.Helper()
	raw, err := os.ReadFile("testdata/canonical-query.signed")
	if err != nil {
		t.Fatalf("testdata/canonical-query.signed: %v", err)
	}
	return strings.TrimRight(string(raw), "\n")
}

func verifyIt(t *testing.T, signed string) (Value, error) {
	t.Helper()
	registry := verifyRegistry(t)
	policy, err := NewSuitePolicy(registry, nil)
	if err != nil {
		t.Fatalf("policy: %v", err)
	}
	return VerifyQuery(signed, policy, registry, verifyResolver(t))
}

// signedHeader builds a compact string with an arbitrary header, signed by key.
// The signature is always valid over the bytes — which is what makes these
// tests about the sequence rather than about the mathematics.
func signedHeader(t *testing.T, header string, key PrivateKey) string {
	t.Helper()
	payload := strings.Split(canonicalSigned(t), ".")[1]
	signingInput := EncodeBase64URL([]byte(header)) + "." + payload
	return signingInput + "." + EncodeBase64URL(key.Sign([]byte(signingInput)))
}

func TestAValidQueryVerifiesAndReturnsTheCoreObject(t *testing.T) {
	core, err := verifyIt(t, canonicalSigned(t))
	if err != nil {
		t.Fatalf("the canonical query verifies: %v", err)
	}
	members, ok := core.(Object)
	if !ok {
		t.Fatal("not an object")
	}
	if _, ok := members["predicate"]; !ok {
		t.Error("no predicate")
	}
	// No signature.value reattached: under this suite it is the third segment
	// and not a member of the object (E-31).
	if _, ok := members["signature"].(Object)["value"]; ok {
		t.Error("signature.value was reattached")
	}
}

func TestTheContainerIsCheckedBeforeTheHeader(t *testing.T) {
	for _, c := range []struct {
		signed string
		want   Rejected
	}{
		{"only.two", CompactSegmentCount},
		{"", CompactSegmentCount},
		{"not base64url!." + strings.SplitN(canonicalSigned(t), ".", 2)[1],
			HeaderSegmentNotBase64URL},
	} {
		_, err := verifyIt(t, c.signed)
		if err != c.want {
			t.Errorf("%q: %v, want %v", c.signed, err, c.want)
		}
	}
}

func TestAHeaderMemberSection3DoesNotPermitIsRefusedAtStep3(t *testing.T) {
	// Issue 12's case, and alg is only the famous instance: the member set is
	// closed, so a header carrying anything extra is refused before the suite is
	// looked up. No rule about alg exists, and none may be added.
	key := keyFor(t, "test-requester-1")
	for _, extra := range []string{`"alg":"none"`, `"alg":"HS256"`, `"crit":["b64"]`, `"b64":false`} {
		header := `{"key_id":"test-requester-1",` + extra + `,"suite":"eddsa-jws-2026"}`
		compact := signedHeader(t, header, key)

		_, err := verifyIt(t, compact)
		if err != HeaderMemberNotPermitted {
			t.Errorf("%s: %v", extra, err)
		}
		if err.(Rejected).Step() != "3" {
			t.Errorf("%s: step %s", extra, err.(Rejected).Step())
		}
		// And it is refused without verifying, which is the point: the signature
		// over these bytes is perfectly good.
		parts := strings.Split(compact, ".")
		signature, _ := DecodeBase64URL(parts[2])
		if e := Verify(key.PublicKey(), []byte(parts[0]+"."+parts[1]), signature); e != nil {
			t.Fatalf("%s: the signature should be valid: %v", extra, e)
		}
	}
}

func TestASuiteOutsideTheAcceptableSetIsRefusedBeforeVerification(t *testing.T) {
	// Step 2. The signature is valid, and the message is refused anyway.
	compact := signedHeader(t,
		`{"key_id":"test-requester-1","suite":"hmac-sha1-1999"}`, keyFor(t, "test-requester-1"))
	_, err := verifyIt(t, compact)
	if err != SuiteUnregistered {
		t.Fatalf("%v", err)
	}
	if got := err.(Rejected).ExternalReason(); got != "unsupported_suite" {
		t.Errorf("external reason %q", got)
	}
}

func TestAnUnresolvableKeyIsIndistinguishableOnTheWireFromABadSignature(t *testing.T) {
	// §4.6's second invariant, at the sequence level. The two reach *different*
	// internal reasons — an operator needs to know which — and the same wire
	// value, which is where the requester's view is collapsed.
	unresolvable := signedHeader(t,
		`{"key_id":"nobody-we-know","suite":"eddsa-jws-2026"}`, keyFor(t, "test-requester-1"))

	signed := canonicalSigned(t)
	last := "A"
	if strings.HasSuffix(signed, "A") {
		last = "B"
	}
	tampered := signed[:len(signed)-1] + last

	// Different internal reasons, and the same wire value — which is the
	// separation §5.2 requires, in the direction that matters.
	_, a := verifyIt(t, unresolvable)
	_, b := verifyIt(t, tampered)
	if a != KeyUnresolvable || b != SignatureInvalid {
		t.Fatalf("%v, %v", a, b)
	}
	if a.(Rejected).ExternalReason() != b.(Rejected).ExternalReason() {
		t.Error("the two are distinguishable on the wire")
	}
}

func TestAHeaderThatDisagreesWithThePayloadIsRefusedAfterVerification(t *testing.T) {
	// Issue 7. The header names a key the payload does not, and the signature is
	// made with that key — so verification succeeds and nothing else would catch
	// it.
	compact := signedHeader(t,
		`{"key_id":"test-requester-2","suite":"eddsa-jws-2026"}`, keyFor(t, "test-requester-2"))
	_, err := verifyIt(t, compact)
	if err != HeaderPayloadKeyMismatch {
		t.Fatalf("%v", err)
	}
	if got := err.(Rejected).ExternalReason(); got != "structurally_invalid" {
		t.Errorf("external reason %q", got)
	}
}

func TestTheMappingToAWireValueIsManyToOneAndNotTheName(t *testing.T) {
	// §5.2's separation. The check is not that the two spell differently —
	// Unauthenticated and unauthenticated coincide, and §5.2.1 names that class
	// after its value on purpose. It is that the wire value is a mapping rather
	// than the constant's name in lower case, and this table is what both
	// implementations must agree on.
	mapping := []struct {
		rejected Rejected
		external string
		step     string
	}{
		{CompactSegmentCount, "structurally_invalid", "3"},
		{HeaderSegmentNotBase64URL, "structurally_invalid", "3"},
		{PayloadSegmentNotBase64URL, "structurally_invalid", "3"},
		{SignatureSegmentNotBase64URL, "structurally_invalid", "3"},
		{HeaderNotAnObject, "structurally_invalid", "3"},
		{HeaderMemberNotAString, "structurally_invalid", "3"},
		{HeaderMemberNotPermitted, "structurally_invalid", "3"},
		{SuiteUnregistered, "unsupported_suite", "3"},
		{SuiteWithdrawnByRegistry, "unsupported_suite", "3"},
		{SuiteBelowPolicy, "unsupported_suite", "3"},
		{KeyUnresolvable, "unauthenticated", "4"},
		{SignatureInvalid, "unauthenticated", "4"},
		{CoreObjectMalformed, "malformed", "5"},
		{CoreObjectCarriesSignatureValue, "malformed", "5"},
		{CoreObjectDuplicateKey, "malformed", "5"},
		{CoreObjectFloat, "malformed", "5"},
		{CoreObjectTooDeep, "malformed", "5"},
		{CoreObjectTooManyMembers, "malformed", "5"},
		{CoreObjectStringTooLong, "malformed", "5"},
		{UnsupportedVersion, "unsupported_version", "5"},
		{HeaderPayloadSuiteMismatch, "structurally_invalid", "5a"},
		{HeaderPayloadKeyMismatch, "structurally_invalid", "5a"},
	}

	// The table covers the type. Without this it covers whatever it covered on
	// the day it was written — and the Rust side's equivalent table carried one
	// reason twice for exactly that reason.
	if len(mapping) != int(rejectedCount) {
		t.Fatalf("the table has %d rows and there are %d reasons", len(mapping), rejectedCount)
	}
	seen := map[Rejected]bool{}
	for _, c := range mapping {
		seen[c.rejected] = true
	}
	for r := Rejected(0); r < rejectedCount; r++ {
		if !seen[r] {
			t.Errorf("reason %v has no row in the table", r)
		}
	}

	values := map[string]struct{}{}
	for _, c := range mapping {
		if got := c.rejected.ExternalReason(); got != c.external {
			t.Errorf("%v: external %q, want %q", c.rejected, got, c.external)
		}
		if got := c.rejected.Step(); got != c.step {
			t.Errorf("%v: step %s, want %s", c.rejected, got, c.step)
		}
		values[c.external] = struct{}{}

		// No rejection's message carries anything from the message it is about.
		message := c.rejected.Error()
		if strings.Contains(message, "test-requester") || strings.Contains(message, "eddsa") {
			t.Errorf("%v: message carries a value: %s", c.rejected, message)
		}
	}

	// Many-to-one, which is the direction that is correct.
	if len(values) >= len(mapping) {
		t.Error("every internal reason has its own wire value, which is the leak")
	}
	if len(values) != 5 {
		t.Errorf("%d distinct wire values", len(values))
	}
}

func TestAVersionThisBuildDoesNotImplementIsRefusedAtStep5(t *testing.T) {
	// message/reject/unknown-version in miniature. The version is inside the
	// signed object, so this is reachable only after verification — which is why
	// it is step 5 and why routing's copy is load shedding rather than a
	// rejection reason.
	raw, err := os.ReadFile("testdata/canonical-query.json")
	if err != nil {
		t.Fatalf("the canonical query: %v", err)
	}
	query, err := Parse(raw)
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	members := query.(Object)
	members["q2d_version"] = String("0.2")
	payload, err := Serialize(members)
	if err != nil {
		t.Fatalf("serialize: %v", err)
	}

	key := keyFor(t, "test-requester-1")
	signingInput := EncodeBase64URL([]byte(`{"key_id":"test-requester-1","suite":"eddsa-jws-2026"}`)) +
		"." + EncodeBase64URL(payload)
	compact := signingInput + "." + EncodeBase64URL(key.Sign([]byte(signingInput)))

	_, err = verifyIt(t, compact)
	if err != UnsupportedVersion {
		t.Fatalf("%v", err)
	}
	if got := err.(Rejected).ExternalReason(); got != "unsupported_version" {
		t.Errorf("external reason %q", got)
	}
	if got := err.(Rejected).Step(); got != "5" {
		t.Errorf("step %q", got)
	}
}

func TestAHeaderWrongInTwoWaysReachesOneReasonEveryTime(t *testing.T) {
	// Go randomizes map iteration and Rust walks a BTreeMap in key order, so a
	// header carrying an extra member *and* a member of the wrong type could
	// otherwise reach a different internal reason on different runs — and a
	// different one from Rust. The wire value collapses them; the corpus asserts
	// the internal reason.
	header := `{"alg":"none","key_id":"test-requester-1","suite":1}`
	first, _ := verifyIt(t, signedHeader(t, header, keyFor(t, "test-requester-1")))
	_ = first
	for i := 0; i < 200; i++ {
		_, err := verifyIt(t, signedHeader(t, header, keyFor(t, "test-requester-1")))
		if err != HeaderMemberNotPermitted {
			t.Fatalf("run %d reached %v", i, err)
		}
	}
}
