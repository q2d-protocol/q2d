// JWS compact construction — P-003 issue 5.
//
//	signed        = BASE64URL(header) "." BASE64URL(payload) "." BASE64URL(signature)
//	signing_input = ASCII(BASE64URL(header) "." BASE64URL(payload))
//
// crypto-suites.md §3 defines the container and the protected header's two
// members. The payload is the byte string Serialize produced; this file never
// builds one and never inspects one.
//
// # Deterministic, which is what the corpus rests on
//
// Ed25519 is deterministic and Serialize is a fixed profile, so the same key and
// the same logical query produce the same compact string every time and in both
// languages. That is why suite/sign/ can assert bytes rather than merely check
// that the result verifies — and a both-verify acceptance would pass two
// implementations that disagree about what they emit, which is exactly the
// divergence Stage 1's gate exists to find.
//
// # The header is serialized, not formatted
//
// Its two members go through Serialize like anything else, so key_id precedes
// suite by the ordering serialization.md §1 fixes. Writing the JSON by hand here
// would put a second serializer in the package whose output has to match the
// first one's — which is the arrangement two implementations drift in.
package q2d

import (
	"fmt"
	"strings"
)

// protectedHeader builds the header crypto-suites.md §3 defines.
//
// Exactly two members, and no others. The set is closed because the header is
// read before verification, so every member is a pre-authentication input
// surface — and because a header a general-purpose JOSE library can process is
// one where that library selects the verification algorithm from
// attacker-controlled data.
func protectedHeader(suite, keyID string) Value {
	return Object{"key_id": String(keyID), "suite": String(suite)}
}

// SignCompact signs payload, producing the compact serialization.
//
// payload is bytes and stays bytes: this function signs what it is handed. The
// caller produced it with Serialize, and re-serializing here would mean two
// paths to the signed bytes with nothing holding them together.
//
// Takes the registry entry, not a suite identifier. crypto-suites.md §6 refuses
// production under a deprecated or withdrawn suite, and a signature taking a
// bare string would let a caller sign under one by naming it — the check would
// exist somewhere else and be forgotten here. Resolving the suite is how you get
// an entry, so the status is in hand by construction.
func SignCompact(payload []byte, key PrivateKey, suite SuiteEntry, keyID string) (string, error) {
	if !suite.Status.MayProduce() {
		// The asymmetry in §6: this same suite may still verify. Refusing here
		// and not there is the whole point, because receipts signed under it
		// remain evidence.
		return "", fmt.Errorf("`%s` may not be produced under: crypto-suites.md "+
			"§6 permits production under an active suite only", suite.ID)
	}
	header, err := Serialize(protectedHeader(suite.ID, keyID))
	if err != nil {
		return "", fmt.Errorf("the protected header does not serialize: %w", err)
	}
	// ASCII by construction: base64url's alphabet and a dot.
	signingInput := EncodeBase64URL(header) + "." + EncodeBase64URL(payload)
	signature := key.Sign([]byte(signingInput))
	return signingInput + "." + EncodeBase64URL(signature), nil
}

// compactSegments splits a compact serialization into its three segments.
//
// Structural only — nothing here verifies anything, and a caller that used the
// payload without verifying first would be violating core-model.md §4's
// ordering. VerifyCompact is how a payload is obtained.
func compactSegments(compact string) (header, payload, signature string, err error) {
	parts := strings.Split(compact, ".")
	if len(parts) != 3 {
		// Two segments, four segments, none: all the same answer. A compact
		// serialization has three, and the count is not negotiable.
		return "", "", "", ErrSignatureInvalid
	}
	return parts[0], parts[1], parts[2], nil
}

// VerifyCompact verifies a compact serialization and returns the payload bytes.
//
// Bytes rather than a parsed object, deliberately (P-003 §9 item 7): core-model.md §4 steps
// 4–5 require verification before parsing, and returning bytes makes that a
// type-level fact. There is no way to obtain a parsed core object from this file
// without having verified it first.
//
// This is not §4.2's four-step sequence — it does not read the suite, does not
// consult a policy, and does not compare the header against the payload. Those
// need P-003 issue 6, which waits on E-46. What this does is the cryptographic
// half, so that issue 6 is the ordering and the policy rather than the ordering,
// the policy and the mathematics.
func VerifyCompact(compact string, key PublicKey) ([]byte, error) {
	header, payload, signature, err := compactSegments(compact)
	if err != nil {
		return nil, err
	}
	// All three segments must be base64url, including the one this function does
	// not read. crypto-suites.md §3 defines the form as BASE64URL(header) "."
	// BASE64URL(payload) "." BASE64URL(signature), and a producer chooses its own
	// header text — so without this, a signature over a malformed header verifies
	// and this returns a payload from a message that is not a Q2D signed string.
	// The caller would fail later trying to read the suite out of it, which is a
	// different function's job and not a reason to hand it bytes.
	if _, err := DecodeBase64URL(header); err != nil {
		return nil, ErrSignatureInvalid
	}
	raw, err := DecodeBase64URL(signature)
	if err != nil {
		return nil, ErrSignatureInvalid
	}
	// The signing input is the received text of the first two segments, not a
	// re-encoding of what they decode to. Re-encoding would make verification
	// depend on this implementation's encoder agreeing with the sender's, which
	// is the canonicalization dependency signing received bytes exists to
	// remove.
	signingInput := compact[:len(header)+1+len(payload)]
	if err := Verify(key, []byte(signingInput), raw); err != nil {
		return nil, err
	}
	decoded, err := DecodeBase64URL(payload)
	if err != nil {
		return nil, ErrSignatureInvalid
	}
	return decoded, nil
}
