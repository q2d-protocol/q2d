package q2d

import (
	"bytes"
	"errors"
	"testing"
)

func aKey(t *testing.T) ([]byte, PrivateKey) {
	t.Helper()
	seed := bytes.Repeat([]byte{7}, 32)
	key, err := NewPrivateKey(seed)
	if err != nil {
		t.Fatalf("key: %v", err)
	}
	return key.PublicKey().Bytes(), key
}

func TestAKnownKeyResolves(t *testing.T) {
	public, _ := aKey(t)
	resolver := NewFixedKeys()
	if err := resolver.Add("test-requester-1", public); err != nil {
		t.Fatalf("add: %v", err)
	}
	got, err := resolver.Resolve("test-requester-1")
	if err != nil || !bytes.Equal(got.Bytes(), public) {
		t.Errorf("resolve: %x, %v", got.Bytes(), err)
	}
}

func TestAnUnknownKeyIsARejectionAndNotADefault(t *testing.T) {
	public, _ := aKey(t)
	resolver := NewFixedKeys()
	_ = resolver.Add("test-requester-1", public)
	if _, err := resolver.Resolve("someone-else"); err == nil {
		t.Error("an unknown key resolved")
	}
	// And an empty resolver resolves nothing rather than everything, which is
	// the direction a "fall back to the only key" convenience fails in.
	if _, err := NewFixedKeys().Resolve("test-requester-1"); err == nil {
		t.Error("an empty resolver resolved a key")
	}
}

func TestTheFailureIsTheSameValueABadSignatureProduces(t *testing.T) {
	// §4.6's second invariant. These are not merely equal today — they are the
	// same sentinel, so there is no second value for a caller to map onto a
	// second wire response.
	public, key := aKey(t)
	resolver := NewFixedKeys()
	_ = resolver.Add("test-requester-1", public)

	_, unresolvable := resolver.Resolve("someone-else")
	badSignature := Verify(key.PublicKey(), []byte("a message"), make([]byte, 64))
	if !errors.Is(unresolvable, ErrSignatureInvalid) || !errors.Is(badSignature, ErrSignatureInvalid) {
		t.Fatalf("not the same sentinel: %v, %v", unresolvable, badSignature)
	}
	if unresolvable.Error() != badSignature.Error() {
		t.Errorf("distinguishable: %q vs %q", unresolvable, badSignature)
	}
}

func TestAKeyTheSuiteWouldRefuseNeverEntersTheSet(t *testing.T) {
	// The identity point. Rejected at insertion, so it cannot resolve and then
	// fail verification — one refusal, at the boundary, rather than two chances
	// to get it right.
	identity := make([]byte, 32)
	identity[0] = 1
	if err := NewFixedKeys().Add("attacker", identity); err == nil {
		t.Error("a small-order key entered the set")
	}
}
