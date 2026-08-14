package q2d

// digest = "sha256:" + lowercase_hex(SHA-256(bytes)) — P-002 §4.7.
//
// The algorithm prefix is mandatory, so a digest is self-describing and a future
// algorithm is additive rather than ambiguous. Changing the encoding changes
// every receipt, which is why §9.6 makes it an escalation.
//
// # Which four
//
// request_digest, response_digest, effective_contract_digest,
// public_context_digest. Only the first digests received bytes with no
// re-serialization — it covers the exact signed bytes of the query, which is
// what makes it checkable by anyone holding the envelope. The other three digest
// a sub-object and therefore need §4.2's production profile, which is why that
// profile applies beyond the payload.
//
// This file is the construction. Which bytes go into each of the four is P-011's
// and P-012's, and response_digest in particular is not the symmetric thing its
// name suggests: the receipt travels inside the response and carries the digest,
// so digesting the whole response would include the digest itself. P-011 §4.2 is
// authoritative.
//
// # crypto/sha256 here, hand-written in Rust
//
// Rust's standard library has no SHA-256 and that crate takes no dependencies,
// so src/digest.rs implements FIPS 180-4 and gates it on the published known
// answers. Go has one in the standard library and uses it.
//
// The asymmetry is deliberate rather than untidy: the shared fixture holds both
// to the same bytes, so a defect in the hand-written one shows up as a
// disagreement with a standard library rather than as two copies of the same
// mistake. That is the opposite of the serializer, where encoding/json had
// behaviours the profile forbids and the standard library was the thing to
// avoid — the question is never "stdlib or not" but "does the stdlib do what
// the specification says".

import (
	"crypto/sha256"
	"encoding/hex"
)

// Digest returns a digest of bytes, as §4.7 spells it.
func Digest(bytes []byte) string {
	sum := sha256.Sum256(bytes)
	// hex.EncodeToString is lowercase and fixed width, which is what §4.7 asks
	// for: a formatter that dropped a leading zero would give a 63-character
	// digest for one input in 256.
	return "sha256:" + hex.EncodeToString(sum[:])
}
