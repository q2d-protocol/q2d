// The suite registry, loaded from a file rather than compiled in.
//
// P-003 issue 3. crypto-suites.md §2 fixes the entry fields and §6 the status
// rules; this file reads them.
//
// # Why a file, for one entry
//
// Adding a second suite becomes a data change rather than a code change in two
// languages — and, more to the point, the pinning and status-checking paths run
// from the first day instead of being retrofitted when they matter. A pinning
// path that has never run is a pinning path that does not work.
//
// # Presence is not acceptance
//
// Resolving a suite here says the protocol knows it and what its status is. It
// does not say a verifier will accept it: that is policy.go, which is local
// configuration and is never derived from a message. The two are separate types
// so that a caller cannot use one where it needs the other — §4.2 step 2 is the
// whole downgrade defence and it reads the policy, not this.
//
// # Status is read, never assumed
//
// SuiteStatus is parsed from the file and an unrecognized value is a load
// failure rather than a default. A registry naming a status this build does not
// understand is one whose rules this build cannot apply, and guessing is how a
// withdrawn suite gets treated as usable.
package q2d

import (
	"fmt"
	"sort"
)

// SuiteStatus is what a registry says may be done with a suite —
// crypto-suites.md §6.
type SuiteStatus string

const (
	SuiteActive     SuiteStatus = "active"
	SuiteDeprecated SuiteStatus = "deprecated"
	SuiteWithdrawn  SuiteStatus = "withdrawn"
)

// MayProduce reports whether a producer may sign under this suite.
//
// The asymmetry with MayVerify is the point: a deprecated suite still verifies
// because receipts signed under it remain evidence.
func (s SuiteStatus) MayProduce() bool {
	return s == SuiteActive
}

// MayVerify reports whether a verifier may accept a signature under this suite.
func (s SuiteStatus) MayVerify() bool {
	return s == SuiteActive || s == SuiteDeprecated
}

// SuiteEntry is one registry entry.
//
// Its fields are not exported, and that is load-bearing. SignCompact takes an
// entry rather than an identifier so that crypto-suites.md §6's producing rule
// cannot be bypassed by naming a suite — and that only holds if an entry cannot
// be built. With exported fields a caller could write
// SuiteEntry{ID: "withdrawn-suite", Status: SuiteActive} and sign under it,
// which is the check restated rather than enforced.
//
// So the only origin is SuiteRegistry.Resolve, exactly as Routing's only origin
// is the projection (P-002 §4.5). The honest limit is the same one P-002 §8
// records: code inside this package can still construct one, and what the type
// removes is the accident rather than the determined bypass.
type SuiteEntry struct {
	id            string
	algorithm     string
	serialization string
	hash          string
	status        SuiteStatus
}

// ID returns the suite identifier — the value a receipt records
// (crypto-suites.md §5), and P-003 issue 13's whole seam.
func (e SuiteEntry) ID() string { return e.id }

// Status returns what may be done with this suite.
func (e SuiteEntry) Status() SuiteStatus { return e.status }

// Algorithm returns the algorithm as the registry describes it. Descriptive:
// nothing selects a verification path from this string — §4.2 step 3 takes
// parameters from the entry the identifier resolved to, never from text in a
// message.
func (e SuiteEntry) Algorithm() string { return e.algorithm }

// Serialization returns how signed bytes are derived, as the registry describes
// it.
func (e SuiteEntry) Serialization() string { return e.serialization }

// Hash returns the hash, where the algorithm does not fix one.
func (e SuiteEntry) Hash() string { return e.hash }

// SuiteRegistry is a loaded registry.
type SuiteRegistry struct {
	entries map[string]SuiteEntry
}

func registryMember(v Value, name string) (Value, error) {
	object, ok := v.(Object)
	if !ok {
		return nil, fmt.Errorf("`%s` is not inside an object", name)
	}
	found, ok := object[name]
	if !ok {
		return nil, fmt.Errorf("no `%s` in the suite registry", name)
	}
	return found, nil
}

func registryText(v Value, name string) (string, error) {
	found, err := registryMember(v, name)
	if err != nil {
		return "", err
	}
	s, ok := found.(String)
	if !ok {
		return "", fmt.Errorf("`%s` is not a string", name)
	}
	return string(s), nil
}

// LoadSuiteRegistry loads a registry from its bytes.
//
// Parsed with this package's own Parse, not encoding/json: this file decides
// which algorithms a verifier accepts, so it is read by the parser that refuses
// duplicate keys rather than one that resolves them by last-wins. A registry
// with status twice is not a registry with one of them.
func LoadSuiteRegistry(raw []byte) (SuiteRegistry, error) {
	document, err := Parse(raw)
	if err != nil {
		return SuiteRegistry{}, fmt.Errorf("the suite registry does not parse: %w", err)
	}
	listed, err := registryMember(document, "suites")
	if err != nil {
		return SuiteRegistry{}, err
	}
	suites, ok := listed.(Array)
	if !ok {
		return SuiteRegistry{}, fmt.Errorf("`suites` is not an array")
	}

	entries := make(map[string]SuiteEntry, len(suites))
	for _, suite := range suites {
		id, err := registryText(suite, "id")
		if err != nil {
			return SuiteRegistry{}, err
		}
		declared, err := registryText(suite, "status")
		if err != nil {
			return SuiteRegistry{}, err
		}
		status := SuiteStatus(declared)
		switch status {
		case SuiteActive, SuiteDeprecated, SuiteWithdrawn:
		default:
			// Fail-closed. A status this build does not understand is one whose
			// rules it cannot apply, and defaulting to active is how a
			// withdrawn suite becomes usable.
			return SuiteRegistry{}, fmt.Errorf(
				"`%s` is not a status crypto-suites.md §6 defines", declared)
		}

		// Every field crypto-suites.md §2 lists must be present, not only the
		// five this type reads. A registry missing withdrawn_from is one whose
		// author did not fill in the shape, and the field it omitted is the one
		// that says when verification must stop — so a partial entry is refused
		// rather than read for the parts that happen to be there.
		//
		// Presence, and the type where this reads it. The dates are not
		// interpreted here: §4.4's rules are driven by status, and a
		// date-driven transition is a scheduling question no part of Q2D 0.1
		// answers. Requiring them keeps the registry honest about what it is
		// claiming without inventing a rule about clocks.
		for _, required := range []string{"effective_from", "security_notes", "references"} {
			if _, err := registryMember(suite, required); err != nil {
				return SuiteRegistry{}, err
			}
		}
		for _, nullable := range []string{"deprecated_from", "withdrawn_from"} {
			value, err := registryMember(suite, nullable)
			if err != nil {
				return SuiteRegistry{}, err
			}
			switch value.(type) {
			case Null, String:
			default:
				return SuiteRegistry{}, fmt.Errorf(
					"`%s` is neither a date nor null", nullable)
			}
		}

		entry := SuiteEntry{id: id, status: status}
		for _, field := range []struct {
			name string
			into *string
		}{
			{"algorithm", &entry.algorithm},
			{"serialization", &entry.serialization},
			{"hash", &entry.hash},
		} {
			value, err := registryText(suite, field.name)
			if err != nil {
				return SuiteRegistry{}, err
			}
			*field.into = value
		}

		// A registry naming one identifier twice is ambiguous about that
		// suite's status, which is the field the whole file exists to carry.
		// Parse refuses duplicate keys; two array elements with the same id are
		// a different shape and are refused here.
		if _, seen := entries[id]; seen {
			return SuiteRegistry{}, fmt.Errorf(
				"`%s` is registered twice, so its status is ambiguous", id)
		}
		entries[id] = entry
	}

	if len(entries) == 0 {
		return SuiteRegistry{}, fmt.Errorf(
			"the suite registry is empty, so nothing could verify")
	}
	return SuiteRegistry{entries: entries}, nil
}

// LoadPinnedSuiteRegistry loads a registry whose digest a verifier has pinned.
//
// The digest is checked before the bytes are parsed, which is the same ordering
// core-model.md §4 applies to a signature: an unpinned file is
// attacker-controlled input, and parsing it first would run this package's
// parser over bytes nobody vouched for to learn something the digest already
// decided.
//
// A mismatch is fatal to startup rather than a warning. §4.3's reason is that a
// file deciding which algorithms a verifier accepts is the last one that should
// be unauthenticated — and a warning on that file is a deployment that runs on
// whatever it was handed.
//
// The registry itself is unsigned today, exactly as registry/manifest.json is;
// the signature is P-005's to build and the pinning is here so that the path
// exists before it is load-bearing.
func LoadPinnedSuiteRegistry(raw []byte, expected string) (SuiteRegistry, error) {
	actual := Digest(raw)
	if actual != expected {
		// Neither digest is secret — one is configuration and the other is
		// computed from a file the operator holds — and an operator with a
		// mismatch needs both to tell which of the two is stale.
		return SuiteRegistry{}, fmt.Errorf(
			"suite registry digest is %s, and %s was pinned", actual, expected)
	}
	return LoadSuiteRegistry(raw)
}

// Resolve resolves an identifier to its entry.
//
// Status-aware in the sense that the entry carries its status; it is not a
// policy check. A caller deciding whether to verify asks the entry and the
// policy, in that order, and both must say yes.
func (r SuiteRegistry) Resolve(id string) (SuiteEntry, error) {
	entry, ok := r.entries[id]
	if !ok {
		// The identifier is echoed because it came from a message and is
		// already known to the sender. What is never echoed is which suites are
		// registered — §4.5, and the reason rejection names no alternative.
		return SuiteEntry{}, fmt.Errorf("`%s` is not a registered suite", id)
	}
	return entry, nil
}

// Identifiers returns every registered identifier, for operator tooling and
// tests.
//
// Not for building a rejection message. §4.5: a rejection names no alternative,
// because suggesting one turns every rejection into a probe of local policy.
func (r SuiteRegistry) Identifiers() []string {
	ids := make([]string, 0, len(r.entries))
	for id := range r.entries {
		ids = append(ids, id)
	}
	// Sorted, because map iteration order must never reach an output.
	sort.Strings(ids)
	return ids
}
