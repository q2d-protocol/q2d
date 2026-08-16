// The predicate registry — P-005 issues 1 and 4.
//
// RegistryPins is what a custodian accepted; PredicateManifest is what it read.
// Loading with the pins applied is issue 3 and waits on the manifest being signed
// (issue 2); this file parses and holds, and refuses everything it cannot make
// sense of.
//
// # Parsed with this package's own parser
//
// Not encoding/json, for the reason suites.go gives: this file decides what a
// custodian will evaluate, so it is read by the parser that refuses duplicate
// keys. A manifest carrying capacity twice is not a manifest with one of them,
// and last-wins would let a publisher put the real value second.
//
// # Capacity is read, never computed
//
// core-model.md §3.1: the registry carries the millibit value precisely so that
// implementations cannot disagree, because IEEE-754 does not guarantee a
// correctly-rounded log2. CapacityMillibits returns what the manifest said.
// Nothing here calls log2 and nothing here holds a float.
package q2d

import (
	"fmt"
	"sort"
)

// RegistryPins is what a custodian has accepted — P-005 §4.1's two pins.
//
// Both are required, and they do different jobs. The signing key is
// authentication: the manifest came from a publisher this custodian recognises.
// The digest is authorization: it is this exact content, which this custodian has
// read. The digest is the stronger of the two, and it is what makes a compromised
// registry key an availability problem rather than a disclosure one — a new
// manifest signed with a stolen key does not match the pin.
//
// That property holds only while a custodian never auto-accepts a new digest,
// which is why §4.3 forbids automatic refresh and why nothing in this file
// fetches anything.
//
// There is no constructor taking a message. The same rule as SuitePolicy, carried
// by the type rather than by a comment: the only way in is a list an operator
// wrote down. Fields are unexported so NewRegistryPins is the only origin.
type RegistryPins struct {
	signingKeys    [][32]byte
	manifestDigest string
}

// NewRegistryPins builds from configuration.
//
// signingKeys are raw Ed25519 public keys and manifestDigest is a
// sha256:-prefixed lowercase hex string — serialization.md §5's form, checked
// here so a mistyped pin fails at startup rather than at the first comparison.
//
// An empty key list is refused. A pin set that authenticates nothing would leave
// the digest doing both jobs, and §4.1 requires both.
func NewRegistryPins(signingKeys [][32]byte, manifestDigest string) (RegistryPins, error) {
	if len(signingKeys) == 0 {
		return RegistryPins{}, fmt.Errorf(
			"no registry signing key is pinned, so nothing would authenticate the " +
				"manifest — P-005 §4.1 requires a key pin as well as a digest pin")
	}
	const prefix = "sha256:"
	if len(manifestDigest) <= len(prefix) || manifestDigest[:len(prefix)] != prefix {
		return RegistryPins{}, fmt.Errorf(
			"pinned manifest digest %q does not start with `sha256:` — serialization.md §5",
			manifestDigest)
	}
	hex := manifestDigest[len(prefix):]
	if len(hex) != 64 {
		return RegistryPins{}, fmt.Errorf(
			"pinned manifest digest %q is not 64 hex characters", manifestDigest)
	}
	for i := 0; i < len(hex); i++ {
		c := hex[i]
		if !(c >= '0' && c <= '9') && !(c >= 'a' && c <= 'f') {
			return RegistryPins{}, fmt.Errorf(
				"pinned manifest digest %q is not lowercase hex — serialization.md §5 "+
					"fixes the case, so an upper-case pin would never match a computed "+
					"digest", manifestDigest)
		}
	}
	pins := RegistryPins{manifestDigest: manifestDigest}
	pins.signingKeys = append(pins.signingKeys, signingKeys...)
	return pins, nil
}

// ManifestDigest returns the pinned digest, for the comparison issue 3 will make.
func (p RegistryPins) ManifestDigest() string { return p.manifestDigest }

// AcceptsKey reports whether this key is pinned.
//
// A membership question rather than an accessor returning the list: a caller that
// could read the keys could log them, and while a public key is not secret, which
// publishers a custodian recognises is closer to its local policy than to
// anything a requester should be able to learn.
func (p RegistryPins) AcceptsKey(key [32]byte) bool {
	for _, pinned := range p.signingKeys {
		if pinned == key {
			return true
		}
	}
	return false
}

// KeyCount returns how many keys are pinned, for operator tooling and tests.
func (p RegistryPins) KeyCount() int { return len(p.signingKeys) }

// EntryStatus is what a registry says may be done with a predicate — P-005 §4.6.
type EntryStatus string

const (
	EntryActive     EntryStatus = "active"
	EntryDeprecated EntryStatus = "deprecated"
	EntryRevoked    EntryStatus = "revoked"
)

// Resolvable reports whether a new request may resolve to this entry.
//
// deprecated rejects here, unlike a deprecated cryptographic suite. The asymmetry
// is not an inconsistency: a suite must keep verifying because receipts signed
// under it remain evidence, and a predicate is evaluated fresh on every request,
// so there is no old exchange to keep readable. §4.6 — deprecated and revoked
// differ only in what an operator is being told about intent.
func (s EntryStatus) Resolvable() bool { return s == EntryActive }

// PredicateEntry is one predicate definition.
//
// Fields are unexported and the only origin is PredicateManifest.EntryFor, for
// the reason SuiteEntry's are: a caller able to write
// PredicateEntry{status: EntryActive} could resolve a revoked predicate, which is
// the check restated rather than enforced.
type PredicateEntry struct {
	id                string
	version           string
	status            EntryStatus
	releaseShape      string
	capacityMillibits *int64
	sensitivity       string
	effectiveFrom     string
	revokedFrom       string
	assuranceProfiles []string
	entryDigest       string
}

func (e PredicateEntry) ID() string            { return e.id }
func (e PredicateEntry) Version() string       { return e.version }
func (e PredicateEntry) Status() EntryStatus   { return e.status }
func (e PredicateEntry) ReleaseShape() string  { return e.releaseShape }
func (e PredicateEntry) Sensitivity() string   { return e.sensitivity }
func (e PredicateEntry) EffectiveFrom() string { return e.effectiveFrom }

// RevokedFrom returns the revocation date, and the empty string where there is
// none.
func (e PredicateEntry) RevokedFrom() string { return e.revokedFrom }

// AssuranceProfiles returns a copy, per CONVENTIONS-go.md's deep-copy rule: Rust
// lends this immutably and a Go caller could otherwise rewrite the entry through
// the slice it was handed.
func (e PredicateEntry) AssuranceProfiles() []string {
	out := make([]string, len(e.assuranceProfiles))
	copy(out, e.assuranceProfiles)
	return out
}

// StoredEntryDigest returns the digest of this entry as the manifest stored it.
//
// Stored, not verified. Issue 12 recomputes it and refuses a manifest where any
// is wrong; until that lands this is what the publisher claimed, and the accessor
// is named to keep that distinction visible at every call site rather than only
// here.
func (e PredicateEntry) StoredEntryDigest() string { return e.entryDigest }

// CapacityMillibits returns the entry's disclosure capacity in integer
// millibits, where it has a single value.
//
// The second return is false where the entry's capacity is a table rather than a
// constant — the scheduling predicate's depends on how many candidates the public
// context carries. That is P-008's to evaluate; this file reports which kind the
// entry has and computes nothing.
//
// Integer, and read rather than derived. core-model.md §3.1 keeps the value in
// the registry precisely because IEEE-754 does not guarantee a correctly-rounded
// log2, so two implementations computing it could disagree by a millibit.
func (e PredicateEntry) CapacityMillibits() (int64, bool) {
	if e.capacityMillibits == nil {
		return 0, false
	}
	return *e.capacityMillibits, true
}

type predicateKey struct {
	id      string
	version string
}

// PredicateManifest is a parsed manifest.
type PredicateManifest struct {
	entries             map[predicateKey]PredicateEntry
	capacityUnit        string
	denialNormalization string
}

func manifestMember(v Value, name string) (Value, error) {
	object, ok := v.(Object)
	if !ok {
		return nil, fmt.Errorf("`%s` is not inside an object", name)
	}
	found, ok := object[name]
	if !ok {
		return nil, fmt.Errorf("no `%s` in the manifest", name)
	}
	return found, nil
}

func manifestText(v Value, name string) (string, error) {
	found, err := manifestMember(v, name)
	if err != nil {
		return "", err
	}
	s, ok := found.(String)
	if !ok {
		return "", fmt.Errorf("`%s` is not a string", name)
	}
	return string(s), nil
}

// ParsePredicateManifest parses a manifest's bytes.
//
// This does not verify anything. The signature and digest checks are issue 3's
// load_manifest, and calling this directly is what a test does; a responder does
// not. Named Parse rather than Load so the difference is visible at the call site.
func ParsePredicateManifest(raw []byte) (PredicateManifest, error) {
	document, err := Parse(raw)
	if err != nil {
		return PredicateManifest{}, fmt.Errorf("the manifest does not parse: %w", err)
	}

	// Both are objects carrying their prose alongside the value, so the value is a
	// member rather than the field itself — capacity_unit.name and
	// denial_normalization.external_reason. Read from the document rather than
	// assumed: the first version of this reader took both for strings and every
	// reference-manifest test failed at once, which is the cheap way to find out.
	unitObject, err := manifestMember(document, "capacity_unit")
	if err != nil {
		return PredicateManifest{}, err
	}
	capacityUnit, err := manifestText(unitObject, "name")
	if err != nil {
		return PredicateManifest{}, err
	}
	normalizationObject, err := manifestMember(document, "denial_normalization")
	if err != nil {
		return PredicateManifest{}, err
	}
	denialNormalization, err := manifestText(normalizationObject, "external_reason")
	if err != nil {
		return PredicateManifest{}, err
	}
	if capacityUnit != "millibits" {
		// Not a style preference. core-model.md §3.1 fixes the unit, and a manifest
		// declaring another one is either a different protocol or a mistake;
		// guessing which is how a capacity in bits gets debited as millibits.
		return PredicateManifest{}, fmt.Errorf(
			"`capacity_unit` is `%s`; core-model.md §3.1 fixes it as `millibits`",
			capacityUnit)
	}

	listed, err := manifestMember(document, "predicates")
	if err != nil {
		return PredicateManifest{}, err
	}
	predicates, ok := listed.(Array)
	if !ok {
		return PredicateManifest{}, fmt.Errorf("`predicates` is not an array")
	}

	entries := make(map[predicateKey]PredicateEntry, len(predicates))
	for _, predicate := range predicates {
		entry, err := parsePredicateEntry(predicate)
		if err != nil {
			return PredicateManifest{}, err
		}
		key := predicateKey{entry.id, entry.version}
		// One identifier and version means one definition. Two would make a
		// resolution ambiguous in exactly the field a requester pins.
		if _, seen := entries[key]; seen {
			return PredicateManifest{}, fmt.Errorf(
				"`%s` version `%s` appears twice", key.id, key.version)
		}
		entries[key] = entry
	}
	if len(entries) == 0 {
		return PredicateManifest{}, fmt.Errorf(
			"the manifest has no predicates, so nothing could resolve")
	}
	return PredicateManifest{
		entries:             entries,
		capacityUnit:        capacityUnit,
		denialNormalization: denialNormalization,
	}, nil
}

func parsePredicateEntry(value Value) (PredicateEntry, error) {
	id, err := manifestText(value, "id")
	if err != nil {
		return PredicateEntry{}, err
	}
	version, err := manifestText(value, "version")
	if err != nil {
		return PredicateEntry{}, err
	}
	declared, err := manifestText(value, "status")
	if err != nil {
		return PredicateEntry{}, err
	}
	status := EntryStatus(declared)
	switch status {
	case EntryActive, EntryDeprecated, EntryRevoked:
	default:
		// Fail-closed. A status this build does not understand is one whose rules
		// it cannot apply, and defaulting to active is how a revoked predicate
		// becomes resolvable.
		return PredicateEntry{}, fmt.Errorf("`%s` is not a status P-005 §4.6 defines", declared)
	}

	// Every field terminology.md §3 gives a registry entry must be present, not
	// only the ones this type reads. A manifest missing output_schema is one whose
	// author did not fill in the shape, and reading it for the parts that happen to
	// be there is how a half-written entry reaches evaluation.
	for _, required := range []string{
		"public_context_schema", "private_input_schema", "output_schema",
		"answer_domain", "freshness", "test_vectors",
	} {
		if _, err := manifestMember(value, required); err != nil {
			return PredicateEntry{}, err
		}
	}

	provenance, err := manifestMember(value, "provenance")
	if err != nil {
		return PredicateEntry{}, err
	}
	effectiveFrom, err := manifestText(provenance, "effective_from")
	if err != nil {
		return PredicateEntry{}, err
	}
	revokedValue, err := manifestMember(provenance, "revoked_from")
	if err != nil {
		return PredicateEntry{}, err
	}
	revokedFrom := ""
	switch v := revokedValue.(type) {
	case Null:
	case String:
		revokedFrom = string(v)
	default:
		return PredicateEntry{}, fmt.Errorf("`provenance.revoked_from` is neither a date nor null")
	}

	capacity, err := manifestMember(value, "capacity")
	if err != nil {
		return PredicateEntry{}, err
	}
	unit, err := manifestText(capacity, "unit")
	if err != nil {
		return PredicateEntry{}, err
	}
	if unit != "millibits" {
		return PredicateEntry{}, fmt.Errorf(
			"`%s`'s capacity is in `%s`; core-model.md §3.1 fixes millibits", id, unit)
	}
	// Exactly one of millibits and table, and neither is optional in the sense of
	// may be absent. A constant capacity carries millibits; one that depends on the
	// public context carries table, which the scheduling predicate's does.
	//
	// Absent-means-table is what this first did, and review found it: an entry with
	// neither loaded as a table capacity nobody could evaluate, and an entry with
	// both silently used millibits while a table said otherwise. Both reach P-008
	// as a debit that is missing or wrong, which is Q2D-C-09's whole subject.
	var capacityMillibits *int64
	capacityObject, ok := capacity.(Object)
	if !ok {
		return PredicateEntry{}, fmt.Errorf("`%s`'s `capacity` is not an object", id)
	}
	raw, hasMillibits := capacityObject["millibits"]
	_, hasTable := capacityObject["table"]
	switch {
	case hasMillibits && hasTable:
		return PredicateEntry{}, fmt.Errorf(
			"`%s`'s capacity carries both `millibits` and `table`, so which one a debit "+
				"comes from is undecided", id)
	case !hasMillibits && !hasTable:
		return PredicateEntry{}, fmt.Errorf(
			"`%s`'s capacity carries neither `millibits` nor `table`, so nothing could "+
				"be debited for it", id)
	case hasMillibits:
		n, ok := raw.(Int)
		if !ok {
			return PredicateEntry{}, fmt.Errorf(
				"`%s`'s `capacity.millibits` is not an integer; core-model.md §3.1 keeps "+
					"floating point out of budget accounting", id)
		}
		// Negative is not a small debit, it is a credit — no cardinality yields
		// one, and an entry carrying one would return budget on every answer. Zero
		// is legal: a domain of one value is degenerate rather than malformed, and
		// refusing it would be a rule invented here.
		if int64(n) < 0 {
			return PredicateEntry{}, fmt.Errorf(
				"`%s`'s `capacity.millibits` is %d; a negative capacity would credit "+
					"the budget rather than debit it", id, int64(n))
		}
		millibits := int64(n)
		capacityMillibits = &millibits
	}

	profilesValue, err := manifestMember(value, "assurance_profiles")
	if err != nil {
		return PredicateEntry{}, err
	}
	profiles, ok := profilesValue.(Array)
	if !ok {
		return PredicateEntry{}, fmt.Errorf("`assurance_profiles` is not an array")
	}
	assuranceProfiles := make([]string, 0, len(profiles))
	for _, item := range profiles {
		s, ok := item.(String)
		if !ok {
			return PredicateEntry{}, fmt.Errorf("an assurance profile is not a string")
		}
		assuranceProfiles = append(assuranceProfiles, string(s))
	}

	releaseShape, err := manifestText(value, "release_shape")
	if err != nil {
		return PredicateEntry{}, err
	}
	// sensitivity.class, not sensitivity — the field carries its rationale
	// alongside the class, and the rationale is for a human.
	sensitivityObject, err := manifestMember(value, "sensitivity")
	if err != nil {
		return PredicateEntry{}, err
	}
	sensitivity, err := manifestText(sensitivityObject, "class")
	if err != nil {
		return PredicateEntry{}, err
	}
	entryDigest, err := manifestText(value, "entry_digest")
	if err != nil {
		return PredicateEntry{}, err
	}

	return PredicateEntry{
		id:                id,
		version:           version,
		status:            status,
		releaseShape:      releaseShape,
		capacityMillibits: capacityMillibits,
		sensitivity:       sensitivity,
		effectiveFrom:     effectiveFrom,
		revokedFrom:       revokedFrom,
		assuranceProfiles: assuranceProfiles,
		entryDigest:       entryDigest,
	}, nil
}

// EntryFor looks an entry up by identifier and version.
//
// Not Resolve. This is a map lookup; §4.6's status and effective-date rules and
// §4.5's declared-digest comparison are issue 5's and issue 7's, and a caller
// reaching this directly has skipped them. The name is the warning.
func (m PredicateManifest) EntryFor(id, version string) (PredicateEntry, bool) {
	entry, ok := m.entries[predicateKey{id, version}]
	return entry, ok
}

// DenialNormalization returns the normalized external value this registry
// declares — core-model.md §5.2.1.
//
// Every rejection from step 9 onward uses it, and it is the registry's and not a
// resolved entry's, which is what makes it available in the cases that need it
// most: an unknown predicate never resolves an entry.
func (m PredicateManifest) DenialNormalization() string { return m.denialNormalization }

// CapacityUnit returns the unit capacities are stated in. Always millibits; a
// manifest saying otherwise does not parse.
func (m PredicateManifest) CapacityUnit() string { return m.capacityUnit }

// Identifiers returns every id and version pair, sorted, for operator tooling and
// tests.
//
// Never for building a rejection. §4.7: all nine resolution failures share one
// wire response, because a requester must not learn which predicates a custodian
// supports.
//
// Sorted because map iteration order may never reach an output.
func (m PredicateManifest) Identifiers() [][2]string {
	out := make([][2]string, 0, len(m.entries))
	for key := range m.entries {
		out = append(out, [2]string{key.id, key.version})
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i][0] != out[j][0] {
			return out[i][0] < out[j][0]
		}
		return out[i][1] < out[j][1]
	})
	return out
}

// Len returns how many entries the manifest holds.
func (m PredicateManifest) Len() int { return len(m.entries) }
