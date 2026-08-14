package q2d

// q2d_version, checked at §4 step 5 and before anything else is read.
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

import "fmt"

// Supported is the version this build implements.
//
// One value, not a range. A range implies a negotiation, and §1 has none.
const Supported = "0.1"

// An UnsupportedVersion is a message this build will not interpret.
//
// It carries no value: q2d_version is the sender's own claim, and an unknown one
// is exactly the field this build has no vocabulary for. §5.2.1's external value
// is unsupported_version, which P-009 emits; this is the internal one.
type UnsupportedVersion struct{}

func (UnsupportedVersion) Error() string {
	return fmt.Sprintf("`q2d_version` is absent or not %s — core-model.md §4 step 5", Supported)
}

// CheckVersion reports whether this build interprets the verified core object.
//
// Absent, not a string, and any other value all reject: unknown, missing and
// indeterminate deny.
func CheckVersion(core Value) error {
	pairs, isObject := core.(Object)
	if !isObject {
		return UnsupportedVersion{}
	}
	version, present := pairs["q2d_version"]
	if !present {
		return UnsupportedVersion{}
	}
	if text, isString := version.(String); isString && string(text) == Supported {
		return nil
	}
	return UnsupportedVersion{}
}
