package q2d

// q2d_version, checked at §4 step 5 — and interpreting no other field.
//
// # One version, inside the signed object
//
// P-002 §10's second question, resolved: the envelope carries no version of its
// own. A separate envelope version would be unsigned and therefore rewritable by
// any intermediary, and two version numbers for one message is a negotiation
// surface core-model.md §1 does not have — there is no round trip in which a
// requester could discover which one a responder honours.
//
// §5.2.1 puts unsupported_version at step 5 for the same reason: the
// authoritative value is inside the signed object, so it cannot be read before
// verification at step 4. routing may carry a copy and §4 step 2 may shed stale
// traffic on it, but that is load shedding and never a rejection reason — which
// is why this function takes the verified core object and has no parameter for a
// projection.
//
// # Rejecting without interpreting is the whole rule
//
// A responder that read the rest of an unknown-version message to produce a
// better error has interpreted fields whose meaning it does not know. Version
// n+1 may move a field, change its type, or give the same name another sense; a
// diagnostic built by reading them is a guess presented as fact, and the guess is
// made on attacker-controlled input.
//
// This function reads exactly one key. That is the property, and it is
// structural rather than a discipline a caller keeps.
//
// It is not the stronger claim that nothing is read first. Step 5 is "parse the
// verified core object", so parsing precedes this and may itself reject — a
// duplicate key, a float, a string above §2.8's bound. Those are §5.2.1's
// malformed, which is the other cause that row gives for step 5, so a message
// that never reaches this function is refused under the right external value
// anyway. What this function adds is that once a message has parsed, an unknown
// version is decided without consulting anything else.

import "fmt"

// Supported is the version this build implements.
//
// One value, not a range. A range implies a negotiation, and §1 has none.
const Supported = "0.1"

// A VersionProblem says why a verified core object is not one this build
// interprets.
//
// Two values because §5.2.1 gives them two external ones. That is the opposite
// of routing's two internal reasons, which both normalize to routing_mismatch —
// there, collapsing them on the wire is the point; here, collapsing them in the
// internal value would make the external one unrecoverable, and a requester told
// unsupported_version about a message that simply omitted the field would go
// looking for a version it does not have.
//
// Neither carries a value. q2d_version is the sender's own claim, and an unknown
// one is exactly the field this build has no vocabulary for.
type VersionProblem int

const (
	// VersionMalformed is §5.2.1's malformed: absent, or not a string. §2.2
	// requires the field, and "the verified core object malformed, or missing a
	// field §2 requires" is that row rather than the version one.
	VersionMalformed VersionProblem = iota
	// VersionUnsupported is §5.2.1's unsupported_version: present, a string, and
	// not Supported. The only case in which the sender got the shape right and
	// this build still cannot read the message.
	VersionUnsupported
)

func (p VersionProblem) Error() string {
	if p == VersionUnsupported {
		return fmt.Sprintf("`q2d_version` names a version this build does not "+
			"implement; it implements %s — core-model.md §4 step 5", Supported)
	}
	return "`q2d_version` is absent or is not a string — §2.2 requires it, so " +
		"this is core-model.md §5.2.1's `malformed`"
}

// CheckVersion reports whether this build interprets the verified core object.
//
// Absent, not a string, and any other value all reject: unknown, missing and
// indeterminate deny.
func CheckVersion(core Value) error {
	pairs, isObject := core.(Object)
	if !isObject {
		return VersionMalformed
	}
	version, present := pairs["q2d_version"]
	if !present {
		return VersionMalformed
	}
	text, isString := version.(String)
	if !isString {
		// §2.2 requires a string here, so §5.2.1's malformed row — "missing a
		// field §2 requires" — is the one that applies. Telling a requester
		// unsupported_version would send it looking for a version it does not
		// have.
		return VersionMalformed
	}
	if string(text) == Supported {
		return nil
	}
	// The sender got the shape right, which is the one case §5.2.1 calls
	// unsupported_version.
	return VersionUnsupported
}
