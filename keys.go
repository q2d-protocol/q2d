// Key resolution — the interface, and a fixture implementation for tests.
//
// P-003 issue 9, §4.6. Resolve(keyID) is the entire surface this PRD owns. Where
// a key comes from, how it was established, how it rotates, and whether a
// delegation chain authorizes it are P-014's.
//
// # Two invariants, and they are the reason this is an interface at all
//
// A key that cannot be resolved is a rejection, never a default. No fallback
// key, no "try the last known good", no unauthenticated acceptance. The
// signature of Resolve carries that: it returns a key or an error, and there is
// no third case for a caller to be lenient about.
//
// Its failure is indistinguishable on the wire from a signature failure. Both
// are core-model.md §5.2.1's unauthenticated, because distinguishing them tells a
// requester whether a key is known — which is relationship existence, and is
// disclosure whether or not the exchange proceeds. That is why this file returns
// ErrSignatureInvalid rather than an error of its own: there is no second value
// to accidentally map onto a second response.
//
// # keyID is a lookup, never a locator
//
// §4.1: the identifier is attacker-controlled and read before anything is
// authenticated. A resolver that treated it as a path or a URL would fetch what
// an attacker named, before verifying anything. It indexes a set the
// implementation already trusts, and nothing else.
package q2d

// KeyResolver resolves a key identifier to a public key this implementation
// already trusts.
type KeyResolver interface {
	// Resolve returns the key, or a rejection. There is no third answer.
	Resolve(keyID string) (PublicKey, error)
}

// FixedKeys is a resolver over a fixed set — the test fixture, and the shape
// P-014 replaces.
//
// Test material only, and it says so where it is built: the keys it holds come
// from conformance/keys/ed25519-test-only.json, whose seeds are published in RFC
// 8032 and known to everyone.
type FixedKeys struct {
	keys map[string]PublicKey
}

// NewFixedKeys returns an empty resolver, which resolves nothing.
func NewFixedKeys() *FixedKeys {
	return &FixedKeys{keys: map[string]PublicKey{}}
}

// Add adds a key. It fails if the bytes are not one crypto-suites.md §3 admits —
// a small-order or non-canonically-encoded key never enters the set, so it
// cannot be resolved later and then refused at verification.
func (f *FixedKeys) Add(keyID string, publicKey []byte) error {
	key, err := NewPublicKey(publicKey)
	if err != nil {
		return err
	}
	f.keys[keyID] = key
	return nil
}

// Resolve implements KeyResolver.
func (f *FixedKeys) Resolve(keyID string) (PublicKey, error) {
	key, ok := f.keys[keyID]
	if !ok {
		return PublicKey{}, ErrSignatureInvalid
	}
	// Copied on the way out, so a caller cannot hold the stored slice across a
	// rotation. Bytes already copies; this names the reason.
	return PublicKey{bytes: key.Bytes()}, nil
}
