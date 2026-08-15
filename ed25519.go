// Ed25519 signing and verification, with the acceptance criteria pinned.
//
// P-003 issue 1. See CONVENTIONS-go.md §2 for why this file has a dependency
// when nothing else in the Go implementation does.
//
// # Which signatures verify, stated rather than inherited
//
// "Ed25519" does not name one verification rule. RFC 8032 leaves choices open
// and libraries take them differently, so two conforming implementations can
// disagree about whether a given signature is valid — which for this project is
// not a curiosity but a failure of the thing the two implementations exist to
// demonstrate.
//
// Q2D accepts a signature exactly when all of these hold:
//
//  1. The public key is 32 bytes and decodes to a point on the curve, with a
//     canonical field encoding.
//  2. The signature is 64 bytes. R decodes to a point; S is canonical, meaning
//     S < L.
//  3. Neither A nor R has small order — that is, [8]A and [8]R are not the
//     identity.
//  4. The cofactorless verification equation holds:
//     [S]B = R + [SHA-512(R ‖ A ‖ M) mod L]A.
//
// # Rule 3 is why crypto/ed25519 is not enough on its own
//
// crypto/ed25519.Verify implements rules 1, 2 and 4 and **not** rule 3. With
// A = R = the identity point and S = 0, the equation reduces to
// identity = identity and holds for every message: a universal forgery
// requiring no private key, which Verify accepts and ed25519-dalek's
// verify_strict refuses.
//
// Rust picks the strict rule (P-003 issue 1, E-47), so this file has to reach
// it too. The check is computed rather than looked up: [8]P is compared with
// the identity, which is exactly what dalek's is_weak does. A blacklist of the
// eight small-order encodings would need its own completeness argument, and a
// blacklist that is one entry short fails open.
//
// filippo.io/edwards25519 supplies the point arithmetic. It is the standard
// library's own implementation, published separately by its author, and
// crypto/ed25519 is built on the internal copy of it.
//
// # Not constant-time, and not claimed to be
//
// Verification handles no secret. Signing does, and crypto/ed25519 documents
// its own timing properties; this file adds no branch on key material. What Q2D
// does not claim is resistance to physical side channels — claims.md has no
// such claim and this file does not create one.
package q2d

import (
	"crypto/ed25519"
	"errors"

	"filippo.io/edwards25519"
)

// ErrSignatureInvalid is the only failure this file reports.
//
// One value. The causes are deliberately not distinguished: core-model.md
// §5.2.1 gives one external class for the whole of authentication, and four
// error values invite a caller to map them onto four responses.
var ErrSignatureInvalid = errors.New("signature does not verify")

// PublicKey is a key that has been checked far enough to be worth keeping.
//
// Constructing one runs rule 1 and the A half of rule 3, so a small-order key
// cannot reach Verify at all — the check is at key resolution rather than at
// every call site.
type PublicKey struct {
	bytes []byte
}

// PrivateKey is test material only in this repository — see
// conformance/keys/README.md.
type PrivateKey struct {
	key ed25519.PrivateKey
}

// smallOrder reports whether an encoded point has order dividing 8, i.e.
// whether [8]P is the identity. An encoding that is not a point at all is
// reported as an error, which callers treat the same way.
func smallOrder(encoded []byte) (bool, error) {
	p, err := new(edwards25519.Point).SetBytes(encoded)
	if err != nil {
		return false, err
	}
	cleared := new(edwards25519.Point).MultByCofactor(p)
	return cleared.Equal(edwards25519.NewIdentityPoint()) == 1, nil
}

// NewPublicKey decodes a 32-byte public key, refusing anything rules 1 and 3
// exclude.
func NewPublicKey(raw []byte) (PublicKey, error) {
	if len(raw) != ed25519.PublicKeySize {
		return PublicKey{}, ErrSignatureInvalid
	}
	weak, err := smallOrder(raw)
	if err != nil || weak {
		return PublicKey{}, ErrSignatureInvalid
	}
	// Copied, because a caller holding the slice could otherwise change the key
	// after it was checked.
	return PublicKey{bytes: append([]byte(nil), raw...)}, nil
}

// Bytes returns the 32-byte encoding.
func (k PublicKey) Bytes() []byte {
	return append([]byte(nil), k.bytes...)
}

// NewPrivateKey builds a key from its 32-byte seed, as RFC 8032 §5.1.5 defines
// one.
func NewPrivateKey(seed []byte) (PrivateKey, error) {
	if len(seed) != ed25519.SeedSize {
		return PrivateKey{}, ErrSignatureInvalid
	}
	return PrivateKey{key: ed25519.NewKeyFromSeed(seed)}, nil
}

// PublicKey returns the public key this seed derives.
func (k PrivateKey) PublicKey() PublicKey {
	raw := k.key.Public().(ed25519.PublicKey)
	return PublicKey{bytes: append([]byte(nil), raw...)}
}

// Sign signs message. Ed25519 is deterministic, so the same key and message
// always produce the same 64 bytes — which is what lets the corpus assert a
// signature rather than merely check one.
func (k PrivateKey) Sign(message []byte) []byte {
	return ed25519.Sign(k.key, message)
}

// Verify checks signature over message under key, against the four rules above.
func Verify(key PublicKey, message, signature []byte) error {
	if len(key.bytes) != ed25519.PublicKeySize || len(signature) != ed25519.SignatureSize {
		return ErrSignatureInvalid
	}
	// Rule 3 for R. A was checked when the key was built; checking it again
	// here would be free, and is left out so that there is one place a key is
	// admitted rather than two rules to keep in step.
	weak, err := smallOrder(signature[:32])
	if err != nil || weak {
		return ErrSignatureInvalid
	}
	// Rules 1, 2 and 4. crypto/ed25519 rejects a non-canonical S, which is the
	// half of rule 2 that libraries differ on.
	if !ed25519.Verify(ed25519.PublicKey(key.bytes), message, signature) {
		return ErrSignatureInvalid
	}
	return nil
}
