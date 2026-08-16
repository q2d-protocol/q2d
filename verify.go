// §4.2's four-step sequence — P-003 issues 6, 7 and 12.
//
//  1. Read the declared suite from the protected header's suite member.
//  2. Reject unless it is a member of the verifier's own acceptable set.
//  3. Verify using the parameters of the registry entry for that suite —
//     never parameters taken from the header.
//  4. After verification, confirm the payload's signature.profile equals the
//     header's suite, and signature.key_id equals the header's key_id.
//
// Step 2 is the whole defence. A verifier that verifies with whatever the header
// names has agility in the same sense that an unlocked door has a lock. The
// acceptable set is SuitePolicy, which is local configuration and has no
// constructor taking a message.
//
// Step 4 is not redundant, though both header and payload are covered by the
// signature so neither can be altered without detection. It catches a producer
// that signs a payload declaring one suite using a header declaring another — a
// real implementation bug that no verifier would otherwise notice, and the same
// for the key. Two comparisons, not one: a producer signing with one key while
// the header names another is worse, because the verifier resolved and used the
// header's key, so the signature verifies and nothing downstream knows the
// signed object disagrees about who signed it.
//
// # What the header may not decide
//
// Nothing. It declares; local policy and the registry decide. A header carrying
// any member beyond suite and key_id is rejected before the suite is even looked
// up — including one carrying parameters that would weaken verification, which is
// P-003 issue 12's case. There is no code path that reads a verification
// parameter from a header, so that vector is refused by the closed member set
// rather than by a rule about the parameters it carries.
package q2d

import "strings"

// Rejected is why a message was rejected, as a responder records it locally.
//
// This is the internal reason and never the wire response. They are separate
// values (core-model.md §5.2), and P-009 builds the response from
// ExternalReason rather than from this type's name.
type Rejected int

const (
	// CompactSegmentCount: signed is not three segments.
	CompactSegmentCount Rejected = iota
	// HeaderSegmentNotBase64URL and its siblings: a segment is not base64url.
	// One constant per segment, because an operator debugging this needs to know
	// which — and because the corpus asserts the internal reason, so two causes
	// sharing one would make two vectors indistinguishable in the half that is
	// meant to distinguish them.
	HeaderSegmentNotBase64URL
	PayloadSegmentNotBase64URL
	SignatureSegmentNotBase64URL
	// HeaderMalformed: the header is not an object, or a member is not a string.
	HeaderMalformed
	// HeaderMemberNotPermitted: the header carries a member §3 does not permit.
	HeaderMemberNotPermitted
	// SuiteUnregistered and SuiteBelowPolicy: two constants, one wire value.
	// §5.2.1 gives unsupported_suite for both on purpose — separating them would
	// tell a requester whether the custodian knows a suite it declined, which is
	// the custodian's minimum acceptable policy. An operator still needs to know
	// which, so the internal reasons differ and the mapping collapses them.
	SuiteUnregistered
	SuiteBelowPolicy
	// Unauthenticated: the key did not resolve, or the signature did not verify.
	// One value, because §5.2.1 gives one class for the whole of authentication
	// and two values here would invite two responses.
	Unauthenticated
	// CoreObjectMalformed: the verified payload is not a core object.
	CoreObjectMalformed
	// HeaderPayloadSuiteMismatch, HeaderPayloadKeyMismatch: the header and the
	// payload disagree.
	HeaderPayloadSuiteMismatch
	HeaderPayloadKeyMismatch
)

// ExternalReason is the value a requester receives — core-model.md §5.2.1.
//
// A separate method rather than a field, so that the internal reason and the
// external one cannot be the same variable by accident. Several internal reasons
// map to one external value, which is the direction that is correct; no internal
// reason maps to two.
func (r Rejected) ExternalReason() string {
	switch r {
	case SuiteUnregistered, SuiteBelowPolicy:
		return "unsupported_suite"
	case Unauthenticated:
		return "unauthenticated"
	case CoreObjectMalformed:
		return "malformed"
	default:
		return "structurally_invalid"
	}
}

// Step is the core-model.md §4 step at which this is caught.
//
// A string, because §4's steps are not all numbers: the header/payload
// comparison is step 5a, lettered so the steps below it did not renumber when
// E-35 added it.
func (r Rejected) Step() string {
	switch r {
	case Unauthenticated:
		return "4"
	case CoreObjectMalformed:
		return "5"
	case HeaderPayloadSuiteMismatch, HeaderPayloadKeyMismatch:
		return "5a"
	default:
		return "3"
	}
}

// Error names the reason and never a value from the message.
func (r Rejected) Error() string {
	switch r {
	case CompactSegmentCount:
		return "`signed` is not three segments"
	case HeaderSegmentNotBase64URL:
		return "the header segment is not base64url"
	case PayloadSegmentNotBase64URL:
		return "the payload segment is not base64url"
	case SignatureSegmentNotBase64URL:
		return "the signature segment is not base64url"
	case HeaderMalformed:
		return "the protected header is not an object"
	case HeaderMemberNotPermitted:
		return "the protected header carries a member crypto-suites.md §3 does not permit"
	case SuiteUnregistered:
		return "the declared suite is not registered"
	case SuiteBelowPolicy:
		return "the declared suite is outside the acceptable set"
	case Unauthenticated:
		return "the message is not authenticated"
	case CoreObjectMalformed:
		return "the verified payload is not a core object"
	case HeaderPayloadSuiteMismatch:
		return "the header and payload declare different suites"
	default:
		return "the header and payload declare different keys"
	}
}

// protectedHeaderFields is the header after §3's member set has been checked.
type protectedHeaderFields struct {
	suite, keyID string
}

// readHeader reads the header — step 1, and §3's closed member set.
//
// This runs before anything is authenticated, which is why it reads as little as
// possible: two members, both strings, nothing else permitted. Every member here
// is a pre-authentication input surface.
func readHeader(segment string) (protectedHeaderFields, error) {
	raw, err := DecodeBase64URL(segment)
	if err != nil {
		return protectedHeaderFields{}, HeaderSegmentNotBase64URL
	}
	// The package's own parser: duplicate keys are refused rather than resolved,
	// so a header carrying suite twice is not a header with one of them.
	value, err := Parse(raw)
	if err != nil {
		return protectedHeaderFields{}, HeaderMalformed
	}
	members, ok := value.(Object)
	if !ok {
		return protectedHeaderFields{}, HeaderMalformed
	}

	// Closed. An alg member is rejected here, by the set rather than by a rule
	// naming it — and so is any parameter that would weaken verification, which
	// is issue 12's vector. No special case exists for either, and none may be
	// added.
	for name := range members {
		if name != "suite" && name != "key_id" {
			return protectedHeaderFields{}, HeaderMemberNotPermitted
		}
	}
	text := func(name string) (string, error) {
		s, ok := members[name].(String)
		if !ok {
			return "", HeaderMalformed
		}
		return string(s), nil
	}
	suite, err := text("suite")
	if err != nil {
		return protectedHeaderFields{}, err
	}
	keyID, err := text("key_id")
	if err != nil {
		return protectedHeaderFields{}, err
	}
	return protectedHeaderFields{suite: suite, keyID: keyID}, nil
}

// VerifyQuery verifies a query envelope's signed string, returning the verified
// core object.
//
// The four steps in order. Nothing below step 3 runs for a suite the policy does
// not accept, and nothing below step 4 runs for an unauthenticated message.
func VerifyQuery(signed string, policy SuitePolicy, registry SuiteRegistry,
	resolver KeyResolver) (Value, error) {
	// The container, before the header: a string that is not three segments has
	// no header to read.
	parts := strings.Split(signed, ".")
	if len(parts) != 3 {
		return nil, CompactSegmentCount
	}
	headerSegment, payloadSegment, signatureSegment := parts[0], parts[1], parts[2]

	// Step 1, and the container's other half: all three segments must be
	// base64url, and that is checked here rather than left to verification. A
	// signature segment that will not decode is a fault in the container
	// crypto-suites.md §3 defines, not an authentication failure — E-46, and the
	// corpus is where the two implementations agree on it.
	header, err := readHeader(headerSegment)
	if err != nil {
		return nil, err
	}
	if _, e := DecodeBase64URL(payloadSegment); e != nil {
		return nil, PayloadSegmentNotBase64URL
	}
	if _, e := DecodeBase64URL(signatureSegment); e != nil {
		return nil, SignatureSegmentNotBase64URL
	}

	// Step 2 — the whole defence. Policy first, then the registry: an
	// unregistered suite and one below the floor produce the same value, which is
	// §5.2.1's unsupported_suite being one value for two causes so that a
	// requester cannot learn whether the custodian knows the suite it declined.
	entry, err := registry.Resolve(header.suite)
	if err != nil {
		return nil, SuiteUnregistered
	}
	if !policy.Accepts(header.suite) || !entry.Status().MayVerify() {
		return nil, SuiteBelowPolicy
	}

	// Step 3 — verify with the entry's parameters. The header supplied an
	// identifier and nothing else; entry is what says how to verify, and this
	// build implements exactly one suite, which step 2 has already established.
	key, err := resolver.Resolve(header.keyID)
	if err != nil {
		return nil, Unauthenticated
	}
	payload, err := verifyCompactParts(signed, headerSegment, payloadSegment,
		signatureSegment, key)
	if err != nil {
		return nil, Unauthenticated
	}

	// Step 5 — parse the verified object. Not before: §2.1 is explicit.
	core, err := Parse(payload)
	if err != nil {
		return nil, CoreObjectMalformed
	}

	// Step 5a — the two comparisons. After parsing, because neither can be made
	// before it.
	members, ok := core.(Object)
	if !ok {
		return nil, CoreObjectMalformed
	}
	signature, ok := members["signature"].(Object)
	if !ok {
		return nil, CoreObjectMalformed
	}
	declared := func(name string) (string, error) {
		s, ok := signature[name].(String)
		if !ok {
			return "", CoreObjectMalformed
		}
		return string(s), nil
	}
	profile, err := declared("profile")
	if err != nil {
		return nil, err
	}
	if profile != header.suite {
		return nil, HeaderPayloadSuiteMismatch
	}
	keyID, err := declared("key_id")
	if err != nil {
		return nil, err
	}
	if keyID != header.keyID {
		return nil, HeaderPayloadKeyMismatch
	}

	return core, nil
}
