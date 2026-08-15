// Ed25519 signing and verification, with the acceptance criteria pinned.
//
// P-003 issue 1. See CONVENTIONS-go.md §2 for why this file has a dependency
// when nothing else in the Go implementation does.
//
// # Which signatures verify
//
// crypto-suites.md §3. Four rules, and this file does not restate them — they
// are spec/'s, and a copy here would be a second source of truth that drifts.
//
// What belongs here is which of them the standard library supplies and which
// this file has to apply itself, because that is a fact about the code:
//
//   - crypto/ed25519.Verify gives the canonical S and the verification
//     equation, and the half of rule 1 that decodes the point.
//   - smallOrder is this file's, because Verify does not reject a small-order
//     public key: with A = R = the identity point and S = 0 the equation holds
//     for every message, which is a valid signature over anything with no
//     private key. Rust's verify_strict refuses it and the standard library
//     accepts it, so this is where the two are brought back together. Computed
//     as [8]P == identity rather than looked up in a blacklist, which would
//     need its own completeness argument and fails open when it is an entry
//     short.
//   - canonicalPoint is this file's too, because neither edwards25519 nor
//     ed25519-dalek applies the field-encoding rule, and they accept the same
//     encodings. Written as a byte comparison so that Go and Rust run the
//     identical test rather than two libraries' opinions of it.
//
// filippo.io/edwards25519 supplies the point arithmetic smallOrder needs. It is
// the standard library's own implementation, published separately by its author,
// and crypto/ed25519 is built on the internal copy of it.
//
// testdata/ed25519-acceptance.txt holds both implementations to the same answers
// on the cases RFC 8032 leaves open.
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
// Constructing one runs §3's rule 1 and the A half of rule 3, so a small-order key
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

// fieldOrder is p = 2^255 - 19, little-endian.
var fieldOrder = [32]byte{
	0xed, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
	0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
	0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x7f,
}

// canonicalPoint applies crypto-suites.md §3's field-encoding rule: the
// y-coordinate is below p.
//
// A compressed Edwards point is the y-coordinate in the low 255 bits and the
// sign of x in the top one, so the check is an integer comparison on bytes.
//
// Neither library enforces it. edwards25519.Point.SetBytes accepts a
// non-canonical encoding, ed25519-dalek accepts one, and they accept the same
// ones — so this is not a divergence between the two implementations but a rule
// neither of their libraries applies. Written in bytes rather than reached for
// through the curve library so that Go and Rust run the identical test.
func canonicalPoint(encoded []byte) bool {
	if len(encoded) != 32 {
		return false
	}
	var y [32]byte
	copy(y[:], encoded)
	y[31] &= 0x7f
	for i := 31; i >= 0; i-- {
		if y[i] != fieldOrder[i] {
			return y[i] < fieldOrder[i]
		}
	}
	return false // y == p is not below it
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

// NewPublicKey decodes a 32-byte public key, refusing anything §3's rules 1 and 3
// exclude.
func NewPublicKey(raw []byte) (PublicKey, error) {
	if len(raw) != ed25519.PublicKeySize || !canonicalPoint(raw) {
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
	// Rules 1 and 3 for R. A was checked when the key was built; checking it
	// again here would be free, and is left out so that there is one place a
	// key is admitted rather than two rules to keep in step.
	if !canonicalPoint(signature[:32]) {
		return ErrSignatureInvalid
	}
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
