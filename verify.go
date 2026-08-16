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

import (
	"sort"
	"strings"
)

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
	// HeaderNotAnObject: the header decoded and is not an object.
	HeaderNotAnObject
	// HeaderMemberNotAString: the header is an object and a member is not a
	// string.
	HeaderMemberNotAString
	// HeaderMemberNotPermitted: the header carries a member §3 does not permit.
	HeaderMemberNotPermitted
	// SuiteUnregistered, SuiteWithdrawnByRegistry and SuiteBelowPolicy: three
	// constants, one wire value. §5.2.1 names *two causes* — the suite
	// unregistered, or below the verifier's minimum acceptable policy — and this
	// is not a third. A withdrawn suite is below every conforming verifier's
	// acceptable policy, because crypto-suites.md §6 requires verification to
	// stop accepting it; the second cause already covers it, and nothing here
	// adds to §5.2.1's table.
	//
	// What is split is the internal reason, which §5.2 makes a separate value
	// from the wire response precisely so it can be finer. The registry
	// withdrawing a suite binds every deployment; an acceptable set is local. An
	// operator needs to know which of those refused a message, and a requester
	// must not — separating them on the wire would say whether the custodian
	// knows a suite it declined, which is its minimum acceptable policy.
	//
	// Named for the registry rather than called SuiteWithdrawn because suites.go
	// already has that identifier for the status itself — CONVENTIONS-go.md.
	SuiteUnregistered
	SuiteWithdrawnByRegistry
	SuiteBelowPolicy
	// KeyUnresolvable and SignatureInvalid: separate internal reasons, and the
	// wire value is not.
	//
	// §5.2.1 gives one class for the whole of authentication because
	// distinguishing them tells a requester whether a key is known, which is
	// relationship existence. An operator debugging still needs to know which,
	// and the corpus asserts the internal reason — so this is the same shape as
	// the two suite reasons: two causes, one value, and the collapse happens in
	// the mapping rather than in the type.
	//
	// An earlier version of this file had one constant here, on the reasoning
	// that "two values would invite two responses". That reasoning applies to
	// the wire value and was applied to the wrong half.
	KeyUnresolvable
	SignatureInvalid
	// CoreObjectMalformed: the verified payload does not parse, is not an object,
	// or has no usable signature member.
	//
	// It does NOT yet cover every field §2 requires. §5.2.1's row says a core
	// object missing one is malformed, and checking that is core-object
	// validation rather than suite verification — P-005's, and the corpus's
	// core_object_missing_required_field vector belongs to whoever builds it.
	// Named here because the gap is easier to find at the constant than in a
	// PRD.
	CoreObjectMalformed
	// CoreObjectCarriesSignatureValue: the verified object carries
	// signature.value.
	//
	// Under eddsa-jws-2026 the value is the third compact segment and is
	// therefore not a member of the object the suite serializes — an object
	// containing the signature over itself is not constructible (E-31). A payload
	// carrying one is a shape no conforming producer emits, and returning it
	// would let everything downstream see a core object that cannot exist.
	//
	// malformed rather than structurally_invalid: the fault is in the verified
	// core object, which is the half of §5.2.1's line that malformed covers.
	CoreObjectCarriesSignatureValue
	// The five parse failures message/reject/ keeps apart.
	//
	// All malformed on the wire — §5.2.1 collapses them because each is visible
	// in the message the requester produced — and each a different fact for an
	// operator, which is why Parse reports a cause rather than only a message.
	CoreObjectDuplicateKey
	CoreObjectFloat
	CoreObjectTooDeep
	CoreObjectTooManyMembers
	CoreObjectStringTooLong
	// UnsupportedVersion: q2d_version is a string this build does not implement.
	//
	// Step 5 and not earlier: the authoritative version is inside the signed
	// object, so it cannot be read before verification. routing may carry a copy
	// and §4 step 2 may shed on it, but that is load shedding and never a
	// rejection reason.
	UnsupportedVersion
	// HeaderPayloadSuiteMismatch, HeaderPayloadKeyMismatch: the header and the
	// payload disagree.
	HeaderPayloadSuiteMismatch
	HeaderPayloadKeyMismatch

	// rejectedCount is not a reason. It is the number of them, and it is here
	// rather than written down because a hand-written count stops being the
	// count the moment someone adds a constant above it — silently. The mapping
	// test walks 0..rejectedCount, so a new reason with no table row fails
	// rather than going untested.
	//
	// It is also what makes Step's default safe: a reason added without a row
	// would otherwise report step 3 because nothing said otherwise.
	rejectedCount
)

// ExternalReason is the value a requester receives — core-model.md §5.2.1.
//
// A separate method rather than a field, so that the internal reason and the
// external one cannot be the same variable by accident. Several internal reasons
// map to one external value, which is the direction that is correct; no internal
// reason maps to two.
func (r Rejected) ExternalReason() string {
	switch r {
	case SuiteUnregistered, SuiteWithdrawnByRegistry, SuiteBelowPolicy:
		return "unsupported_suite"
	case KeyUnresolvable, SignatureInvalid:
		return "unauthenticated"
	case CoreObjectMalformed, CoreObjectCarriesSignatureValue,
		CoreObjectDuplicateKey, CoreObjectFloat, CoreObjectTooDeep,
		CoreObjectTooManyMembers, CoreObjectStringTooLong:
		return "malformed"
	case UnsupportedVersion:
		return "unsupported_version"
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
	case KeyUnresolvable, SignatureInvalid:
		return "4"
	case CoreObjectMalformed, CoreObjectCarriesSignatureValue, UnsupportedVersion,
		CoreObjectDuplicateKey, CoreObjectFloat, CoreObjectTooDeep,
		CoreObjectTooManyMembers, CoreObjectStringTooLong:
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
	case HeaderNotAnObject:
		return "the protected header is not an object"
	case HeaderMemberNotAString:
		return "a protected header member is not a string"
	case HeaderMemberNotPermitted:
		return "the protected header carries a member crypto-suites.md §3 does not permit"
	case SuiteUnregistered:
		return "the declared suite is not registered"
	case SuiteWithdrawnByRegistry:
		return "the declared suite is withdrawn"
	case SuiteBelowPolicy:
		return "the declared suite is outside the acceptable set"
	case KeyUnresolvable:
		return "the key did not resolve"
	case SignatureInvalid:
		return "the signature did not verify"
	case CoreObjectMalformed:
		return "the verified payload is not a core object"
	case CoreObjectDuplicateKey:
		return "the verified object has a duplicate key"
	case CoreObjectFloat:
		return "the verified object carries a floating-point value"
	case CoreObjectTooDeep:
		return "the verified object nests past the limit"
	case CoreObjectTooManyMembers:
		return "an object in the payload has too many members"
	case CoreObjectStringTooLong:
		return "a string in the payload is past its limit"
	case CoreObjectCarriesSignatureValue:
		return "the verified object carries `signature.value`, which this suite puts in the third segment"
	case UnsupportedVersion:
		return "the verified object declares a version this build does not implement"
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
		return protectedHeaderFields{}, HeaderNotAnObject
	}
	members, ok := value.(Object)
	if !ok {
		return protectedHeaderFields{}, HeaderNotAnObject
	}

	// Closed. An alg member is rejected here, by the set rather than by a rule
	// naming it — and so is any parameter that would weaken verification, which
	// is issue 12's vector. No special case exists for either, and none may be
	// added.
	//
	// Sorted, because Go randomizes map iteration and Rust walks a BTreeMap in
	// key order. A header that is wrong in two ways at once — an extra member
	// and a member of the wrong type — would otherwise reach a different
	// internal reason on different runs, and a different one from Rust. The wire
	// value collapses them; the corpus asserts the internal reason.
	names := make([]string, 0, len(members))
	for name := range members {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		if name != "suite" && name != "key_id" {
			return protectedHeaderFields{}, HeaderMemberNotPermitted
		}
	}
	text := func(name string) (string, error) {
		s, ok := members[name].(String)
		if !ok {
			return "", HeaderMemberNotAString
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

	// Step 2 — the whole defence.
	//
	// Registry, then status, then policy — the order the three internal reasons
	// can be told apart in. A suite that is not registered has no status to
	// read, and one the registry has withdrawn is refused whatever a deployment
	// configured, so reading policy first would report a local decision for a
	// refusal that was not local. All three reach one wire value — §5.2.1's
	// unsupported_suite, which is one value for its two causes so that a
	// requester cannot learn whether the custodian knows the suite it declined.
	entry, err := registry.Resolve(header.suite)
	if err != nil {
		return nil, SuiteUnregistered
	}
	if !entry.Status().MayVerify() {
		return nil, SuiteWithdrawnByRegistry
	}
	if !policy.Accepts(header.suite) {
		return nil, SuiteBelowPolicy
	}

	// Step 3 — verify with the entry's parameters. The header supplied an
	// identifier and nothing else; entry is what says how to verify, and this
	// build implements exactly one suite, which step 2 has already established.
	key, err := resolver.Resolve(header.keyID)
	if err != nil {
		return nil, KeyUnresolvable
	}
	payload, err := verifyCompactParts(signed, headerSegment, payloadSegment,
		signatureSegment, key)
	if err != nil {
		return nil, SignatureInvalid
	}

	// Step 5 — parse the verified object. Not before: §2.1 is explicit.
	//
	// The five message/reject/ keeps apart. All malformed on the wire and each a
	// different fact for an operator, which is why Parse reports a ParseCause
	// rather than only a message. Recovering them by matching prose would be a
	// second place that decides what a parse failure was.
	core, err := Parse(payload)
	if err != nil {
		switch CauseOf(err) {
		case CauseDuplicateKey:
			return nil, CoreObjectDuplicateKey
		case CauseFloat:
			return nil, CoreObjectFloat
		case CauseTooDeep:
			return nil, CoreObjectTooDeep
		case CauseTooManyMembers:
			return nil, CoreObjectTooManyMembers
		case CauseStringTooLong:
			return nil, CoreObjectStringTooLong
		default:
			// An integer outside int64 and everything RFC 8259 itself refuses
			// are one fact to an operator — this is not a core object — and no
			// vector distinguishes them.
			return nil, CoreObjectMalformed
		}
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

	// After 5a, not before. crypto-suites.md §3 puts the two comparisons
	// "immediately after the payload is parsed… and before any step that acts on
	// a payload field", and q2d_version is a payload field. A message that is
	// both a version this build does not implement and a header/payload
	// disagreement answers with the disagreement.
	//
	// Beyond that ordering, the version is read before anything else in the
	// object: a 0.2 message may have moved or retyped any field, so interpreting
	// one to build a better diagnostic would be a guess presented as fact.
	if problem := CheckVersion(core); problem != nil {
		if problem == error(VersionUnsupported) {
			return nil, UnsupportedVersion
		}
		return nil, CoreObjectMalformed
	}

	// E-31, last: signature.value is one of the fields the version check above
	// means when it says anything else in the object. A payload that is both an
	// unimplemented version and carries a value answers with the version, because
	// under 0.2 the member might not mean what it means here.
	if _, carries := signature["value"]; carries {
		return nil, CoreObjectCarriesSignatureValue
	}

	return core, nil
}
