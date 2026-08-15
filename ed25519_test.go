package q2d

import (
	"bytes"
	"crypto/ed25519"
	"encoding/hex"
	"os"
	"testing"
)

func mustHex(t *testing.T, s string) []byte {
	t.Helper()
	raw, err := hex.DecodeString(s)
	if err != nil {
		t.Fatalf("hex %q: %v", s, err)
	}
	return raw
}

// knownAnswer is one row of RFC 8032 §7.1, read from the committed key material
// rather than repeated here.
//
// conformance/keys/ is the one place a private seed lives — a test asserts that
// over every byte of every file in the repository, and it caught the first
// version of this file doing the obvious thing. The rule earns its keep twice
// over here: the gate now asserts that the material the corpus signs with
// reproduces RFC 8032, which is stronger than asserting it about a copy that
// could drift.
//
// Read with this package's own parser rather than encoding/json, for the reason
// CONVENTIONS-go.md §2 gives: the parser that reads Q2D structures is the one
// that refuses what Q2D refuses, and a test is not a reason to reach for a
// second one.
type knownAnswer struct {
	seed, message, signature []byte
}

func knownAnswers(t *testing.T) []knownAnswer {
	t.Helper()
	raw, err := os.ReadFile("conformance/keys/ed25519-test-only.json")
	if err != nil {
		t.Fatalf("key material: %v", err)
	}
	document, err := Parse(raw)
	if err != nil {
		t.Fatalf("the key material parses: %v", err)
	}

	member := func(v Value, name string) Value {
		object, ok := v.(Object)
		if !ok {
			t.Fatalf("%s is not in an object", name)
		}
		found, ok := object[name]
		if !ok {
			t.Fatalf("no %s", name)
		}
		return found
	}
	text := func(v Value) string {
		s, ok := v.(String)
		if !ok {
			t.Fatalf("expected a string, found %T", v)
		}
		return string(s)
	}

	keys := member(document, "keys")
	rows, ok := member(document, "known_answers").(Array)
	if !ok {
		t.Fatal("known_answers is not an array")
	}
	answers := make([]knownAnswer, 0, len(rows))
	for _, row := range rows {
		seed := text(member(member(keys, text(member(row, "key"))), "seed"))
		answers = append(answers, knownAnswer{
			seed:      mustHex(t, seed),
			message:   mustHex(t, text(member(row, "message"))),
			signature: mustHex(t, text(member(row, "signature"))),
		})
	}
	if len(answers) != 3 {
		t.Fatalf("the key material lost a known answer: %d", len(answers))
	}
	return answers
}

func TestRFC8032KnownAnswers(t *testing.T) {
	for i, c := range knownAnswers(t) {
		key, err := NewPrivateKey(c.seed)
		if err != nil {
			t.Fatalf("answer %d: %v", i, err)
		}
		if got := key.Sign(c.message); !bytes.Equal(got, c.signature) {
			t.Errorf("answer %d: sign = %x", i, got)
		}
		if err := Verify(key.PublicKey(), c.message, c.signature); err != nil {
			t.Errorf("answer %d: verify: %v", i, err)
		}
	}
}

func TestSigningIsDeterministic(t *testing.T) {
	// Not a property of every signature scheme, and the corpus depends on it: a
	// sign_query vector asserts bytes, which is only meaningful because two runs
	// agree.
	key, _ := NewPrivateKey(knownAnswers(t)[0].seed)
	if !bytes.Equal(key.Sign([]byte("the same message")), key.Sign([]byte("the same message"))) {
		t.Error("two signatures over one message differ")
	}
}

func TestASignatureOverAnotherMessageIsRefused(t *testing.T) {
	key, _ := NewPrivateKey(knownAnswers(t)[0].seed)
	if err := Verify(key.PublicKey(), []byte("another message"), key.Sign([]byte("one message"))); err == nil {
		t.Error("accepted")
	}
}

func TestASignatureByAnotherKeyIsRefused(t *testing.T) {
	answers := knownAnswers(t)
	signer, _ := NewPrivateKey(answers[0].seed)
	other, _ := NewPrivateKey(answers[1].seed)
	if err := Verify(other.PublicKey(), []byte("a message"), signer.Sign([]byte("a message"))); err == nil {
		t.Error("accepted")
	}
}

func TestWrongLengthsAreRefused(t *testing.T) {
	if _, err := NewPublicKey(make([]byte, 31)); err == nil {
		t.Error("a 31-byte key was accepted")
	}
	if _, err := NewPublicKey(make([]byte, 33)); err == nil {
		t.Error("a 33-byte key was accepted")
	}
	key, _ := NewPrivateKey(knownAnswers(t)[0].seed)
	for _, n := range []int{63, 65} {
		if err := Verify(key.PublicKey(), nil, make([]byte, n)); err == nil {
			t.Errorf("a %d-byte signature was accepted", n)
		}
	}
}

// The group order, little-endian.
var groupOrder = []byte{
	0xed, 0xd3, 0xf5, 0x5c, 0x1a, 0x63, 0x12, 0x58, 0xd6, 0x9c, 0xf7, 0xa2,
	0xde, 0xf9, 0xde, 0x14, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x10,
}

func TestANonCanonicalSIsRefused(t *testing.T) {
	// Rule 2. S + L is a second encoding of the same scalar, so without this
	// every signature has a twin that verifies — and a signed string that can be
	// altered in transit and still verify.
	key, _ := NewPrivateKey(knownAnswers(t)[0].seed)
	signature := key.Sign(nil)
	if err := Verify(key.PublicKey(), nil, signature); err != nil {
		t.Fatalf("the original does not verify: %v", err)
	}

	twin := append([]byte(nil), signature...)
	carry := 0
	for i := 0; i < 32; i++ {
		sum := int(twin[32+i]) + int(groupOrder[i]) + carry
		twin[32+i] = byte(sum)
		carry = sum >> 8
	}
	if bytes.Equal(twin, signature) {
		t.Fatal("S + L must differ from S")
	}
	if err := Verify(key.PublicKey(), nil, twin); err == nil {
		t.Error("a non-canonical S was accepted")
	}
}

// The identity point, and the point of order two. A = R = identity with S = 0
// satisfies the verification equation for every message.
const (
	identityPoint = "0100000000000000000000000000000000000000000000000000000000000000"
	orderTwoPoint = "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f"
)

func TestASmallOrderKeyIsRefusedBeforeItIsAKey(t *testing.T) {
	// Rule 3, enforced at construction: this never reaches Verify.
	for _, point := range []string{identityPoint, orderTwoPoint} {
		if _, err := NewPublicKey(mustHex(t, point)); err == nil {
			t.Errorf("%s was accepted as a key", point)
		}
	}
}

func TestANonCanonicalFieldEncodingIsRefused(t *testing.T) {
	// Rule 1's other half. y + p for the twelve values above p that are still
	// points on the curve — both libraries accept these, so this is the rule Q2D
	// applies that neither of its dependencies does.
	above := fieldOrder
	above[0] += 3 // y = p + 3
	if _, err := NewPublicKey(above[:]); err == nil {
		t.Error("a non-canonical public key was accepted")
	}

	// And in R, where it reaches Verify rather than key construction.
	key, _ := NewPrivateKey(knownAnswers(t)[0].seed)
	signature := key.Sign(nil)
	forged := append(append([]byte(nil), above[:]...), signature[32:]...)
	if err := Verify(key.PublicKey(), nil, forged); err == nil {
		t.Error("a non-canonical R was accepted")
	}

	// The boundary: y = p - 1 is the largest canonical value and must not be
	// caught by a rule written with <= where it needs <.
	largest := fieldOrder
	largest[0]--
	if !canonicalPoint(largest[:]) {
		t.Error("p - 1 must be canonical")
	}
	if canonicalPoint(fieldOrder[:]) {
		t.Error("p must not be canonical")
	}
}

func TestAcceptanceDiffersFromTheStandardLibrary(t *testing.T) {
	// The whole reason this file exists rather than a call to ed25519.Verify.
	// Under the standard library's rule the identity forgery is a valid
	// signature over any message, by anyone, with no private key.
	raw := mustHex(t, identityPoint)
	forgery := append(mustHex(t, identityPoint), make([]byte, 32)...)

	for _, message := range [][]byte{nil, []byte("any message at all"), []byte("or this one")} {
		if !ed25519.Verify(ed25519.PublicKey(raw), message, forgery) {
			t.Fatal("crypto/ed25519 was expected to accept the forgery")
		}
		// NewPublicKey refuses the key, so the forgery cannot even be presented
		// through this file's interface — which is the refusal.
		if _, err := NewPublicKey(raw); err == nil {
			t.Error("Q2D's rule must refuse the key")
		}
	}
}

func TestASmallOrderRIsRefused(t *testing.T) {
	// Rule 3's other half, which NewPublicKey cannot cover: R travels in the
	// signature. Built against a real key so that the small-order R is the only
	// thing wrong with it.
	key, _ := NewPrivateKey(knownAnswers(t)[0].seed)
	signature := key.Sign(nil)
	forged := append(mustHex(t, identityPoint), signature[32:]...)
	if err := Verify(key.PublicKey(), nil, forged); err == nil {
		t.Error("a small-order R was accepted")
	}
}
