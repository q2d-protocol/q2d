package q2d

import (
	"strings"
	"testing"
)

// These mirror src/version.rs's tests case for case.

func TestTheSupportedVersionPasses(t *testing.T) {
	core := Object{"q2d_version": String(Supported), "type": String("query")}
	if err := CheckVersion(core); err != nil {
		t.Errorf("the supported version: %v", err)
	}
}

func TestAVersionThisBuildDoesNotImplementIsUnsupported(t *testing.T) {
	// A version this build does not implement is not a thing to negotiate: §1
	// has no round trip in which to negotiate it.
	for _, version := range []string{
		// A version from the future, and one from a past that never was.
		"0.2", "0.0",
		// Prefixes and suffixes, which a HasPrefix or trimming check would
		// admit, and none of which is this version.
		"0.10", "0.1.0", " 0.1", "0.1 ",
	} {
		if err := CheckVersion(Object{"q2d_version": String(version)}); err != VersionUnsupported {
			t.Errorf("%q: %v", version, err)
		}
	}
}

func TestAnAbsentOrMistypedVersionIsMalformedRatherThanUnsupported(t *testing.T) {
	// §5.2.1 gives these two rows: "the verified core object malformed, or
	// missing a field §2 requires" is malformed, and only an unknown value is
	// unsupported_version. Collapsing them here would make the external value
	// unrecoverable, and a requester told unsupported_version about a message
	// that omitted the field would go looking for a version it does not have.
	for _, core := range []Value{
		// The number rather than the string: §2.2's field is a string, and a
		// check that coerced would accept a shape the profile refuses.
		Object{"q2d_version": Int(0)},
		Object{"q2d_version": Null{}},
		// Absent, and not an object at all.
		Object{"type": String("query")},
		Null{},
		Array{},
	} {
		if err := CheckVersion(core); err != VersionMalformed {
			t.Errorf("%v: %v", core, err)
		}
	}
}

func TestAnUnknownVersionRejectsWithoutReadingAnythingElse(t *testing.T) {
	// The rule this issue exists for. Every other field here is wrong in a way a
	// later step would catch — a predicate that is a string, a type that is a
	// number — and none of it is consulted, because version n+1 may have moved
	// or retyped any of them and a diagnostic built by reading them is a guess
	// presented as fact.
	//
	// Deliberately not a malformed issued_at: that would be rejected by Parse
	// before this function ever saw it, under §5.2.1's malformed, so it would
	// demonstrate the parser rather than this.
	nonsense := Object{
		"q2d_version": String("0.2"),
		"predicate":   String("not an object"),
		"type":        Int(7),
		"nonce":       Object{"not": String("a nonce")},
	}
	if err := CheckVersion(nonsense); err == nil {
		t.Error("an unknown version was accepted")
	}

	// And the same object with a supported version passes this check, which is
	// what makes the assertion above about the version rather than the nonsense.
	sameShape := Object{
		"q2d_version": String(Supported),
		"predicate":   String("not an object"),
		"type":        Int(7),
		"nonce":       Object{"not": String("a nonce")},
	}
	if err := CheckVersion(sameShape); err != nil {
		t.Errorf("the same shape with a supported version: %v", err)
	}
}

func TestTheMessageCarriesNoValue(t *testing.T) {
	// q2d_version is the sender's claim, and an unknown one is exactly the field
	// this build has no vocabulary for — so repeating it in a log line is
	// repeating something unparsed. The message names the field and the version
	// this build does implement, both of which are ours.
	message := VersionUnsupported.Error()
	if !strings.Contains(message, "q2d_version") || !strings.Contains(message, Supported) {
		t.Errorf("got %s", message)
	}
	// And the malformed one names §2.2's requirement rather than a version.
	malformed := VersionMalformed.Error()
	if !strings.Contains(malformed, "§2.2") || strings.Contains(malformed, "does not implement") {
		t.Errorf("got %s", malformed)
	}
}
