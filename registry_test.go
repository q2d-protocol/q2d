package q2d

import (
	"os"
	"strings"
	"testing"
)

// These mirror src/registry.rs's tests case for case. Two readings of P-005 and
// registry/manifest.json that disagree would be a specification ambiguity found,
// so the cases are deliberately the same and the code deliberately is not shared.

const manifestEntryDigest = "sha256:bd08ff230de0d8ce34de99967f7a9097988b49058f0a21dd35b9444c24098e35"

func referenceManifest(t *testing.T) PredicateManifest {
	t.Helper()
	raw, err := os.ReadFile("registry/manifest.json")
	if err != nil {
		t.Fatalf("registry/manifest.json: %v", err)
	}
	manifest, err := ParsePredicateManifest(raw)
	if err != nil {
		t.Fatalf("the reference manifest parses: %v", err)
	}
	return manifest
}

func TestTheReferenceManifestParses(t *testing.T) {
	manifest := referenceManifest(t)
	if manifest.Len() != 3 {
		t.Errorf("%d predicates", manifest.Len())
	}
	if manifest.CapacityUnit() != "millibits" {
		t.Errorf("capacity unit %q", manifest.CapacityUnit())
	}
	if manifest.DenialNormalization() != "unavailable" {
		t.Errorf("denial normalization %q", manifest.DenialNormalization())
	}
}

func TestAnEntryReportsWhatTheManifestSaid(t *testing.T) {
	entry, ok := referenceManifest(t).EntryFor("https://q2d.dev/predicates/dietary/menu-compatible", "0.1")
	if !ok {
		t.Fatal("absent")
	}
	if entry.Status() != EntryActive {
		t.Errorf("status %q", entry.Status())
	}
	if entry.ReleaseShape() != "boolean" {
		t.Errorf("release shape %q", entry.ReleaseShape())
	}
	millibits, present := entry.CapacityMillibits()
	if !present || millibits != 1000 {
		t.Errorf("capacity %d %v", millibits, present)
	}
	if entry.StoredEntryDigest() != manifestEntryDigest {
		t.Errorf("entry digest %q", entry.StoredEntryDigest())
	}
	if entry.RevokedFrom() != "" {
		t.Errorf("revoked from %q", entry.RevokedFrom())
	}
}

func TestATableCapacityReportsNoSingleValue(t *testing.T) {
	// The scheduling predicate's capacity depends on how many candidates the
	// public context carries, so there is no constant to report. Absent is the
	// honest answer and P-008 evaluates the table; a zero here would be a debit of
	// nothing.
	entry, ok := referenceManifest(t).EntryFor(
		"https://q2d.dev/predicates/scheduling/availability-window", "0.1")
	if !ok {
		t.Fatal("absent")
	}
	if _, present := entry.CapacityMillibits(); present {
		t.Error("a table capacity reported a single value")
	}
}

func TestVersionIsPartOfTheKey(t *testing.T) {
	if _, ok := referenceManifest(t).EntryFor("https://q2d.dev/predicates/dietary/menu-compatible", "0.2"); ok {
		t.Error("a version that does not exist resolved")
	}
}

func TestDeprecatedDoesNotResolveWhereADeprecatedSuiteWouldVerify(t *testing.T) {
	// §4.6's asymmetry, asserted rather than described. A suite keeps verifying
	// because receipts signed under it remain evidence; a predicate is evaluated
	// fresh every time, so there is no old exchange to keep readable.
	if !EntryActive.Resolvable() {
		t.Error("active does not resolve")
	}
	if EntryDeprecated.Resolvable() || EntryRevoked.Resolvable() {
		t.Error("a non-active entry resolves")
	}
	if !SuiteDeprecated.MayVerify() {
		t.Error("a deprecated suite does not verify, so there is no asymmetry to assert")
	}
}

// manifestWith builds a one-entry manifest whose entry digest is correct by
// construction.
//
// The rule is restated here, which is a duplication worth naming: the fixture has
// to be valid for the tests that are about something else, and one carrying a
// wrong digest would fail every one of them for the wrong reason.
//
// What checks the rule itself is not this. It is the reference manifest, whose
// three stored digests were authored by registry/validate.py in Python and now
// recompute in Go and in Rust — three readings of entry_digest_rule that have to
// agree.
func manifestWith(entryPatch string) (PredicateManifest, error) {
	return manifestWithRevocation(entryPatch, "null")
}

func manifestWithRevocation(entryPatch, revokedFrom string) (PredicateManifest, error) {
	body := `{"id":"p","version":"0.1","status":"active",
		"release_shape":"boolean","sensitivity":{"class":"low"},
		"public_context_schema":{},"private_input_schema":{},
		"output_schema":{},"answer_domain":{},"freshness":{},
		"test_vectors":[],"assurance_profiles":["a"],
		"provenance":{"effective_from":"2026-01-01","revoked_from":` + revokedFrom + `},
		` + entryPatch + `}`
	// Digest the entry as the rule says — without entry_digest — then put the
	// result in and wrap it in a manifest.
	entry, err := Parse([]byte(body))
	if err != nil {
		return PredicateManifest{}, err
	}
	serialized, err := Serialize(entry)
	if err != nil {
		return PredicateManifest{}, err
	}
	raw := `{"capacity_unit":{"name":"millibits"},
		"denial_normalization":{"external_reason":"unavailable"},
		"predicates":[` + body[:len(body)-1] + `,"entry_digest":"` + Digest(serialized) + `"}]}`
	return ParsePredicateManifest([]byte(raw))
}

func TestACapacityThatIsNotAnIntegerIsRefused(t *testing.T) {
	// §3.1 keeps floating point out of budget accounting, and a manifest is where
	// one would enter.
	_, err := manifestWith(`"capacity":{"unit":"millibits","millibits":1000.5}`)
	if err == nil {
		t.Fatal("a floating-point capacity was accepted")
	}
	if !strings.Contains(err.Error(), "integer") {
		t.Errorf("%v", err)
	}
}

func TestACapacityMustCarryExactlyOneOfMillibitsAndTable(t *testing.T) {
	// Review found both halves. Neither is a shape a publisher writes on purpose,
	// and both reach P-008 as a debit that is missing or wrong.
	_, neither := manifestWith(`"capacity":{"unit":"millibits"}`)
	if neither == nil || !strings.Contains(neither.Error(), "neither") {
		t.Errorf("capacity with no source: %v", neither)
	}
	_, both := manifestWith(`"capacity":{"unit":"millibits","millibits":1000,"table":{"2":1000}}`)
	if both == nil || !strings.Contains(both.Error(), "both") {
		t.Errorf("capacity with two sources: %v", both)
	}
	if _, err := manifestWith(`"capacity":{"unit":"millibits","millibits":1000}`); err != nil {
		t.Errorf("a constant capacity was refused: %v", err)
	}
	if _, err := manifestWith(`"capacity":{"unit":"millibits","table":{"2":1000}}`); err != nil {
		t.Errorf("a table capacity was refused: %v", err)
	}
}

func TestANegativeCapacityIsRefusedAndZeroIsNot(t *testing.T) {
	// A negative capacity is not a small debit, it is a credit: an entry carrying
	// one would return budget on every answer. Zero is legal — a domain of one
	// value is degenerate rather than malformed, and refusing it would be a rule
	// invented here rather than read from §3.1.
	_, err := manifestWith(`"capacity":{"unit":"millibits","millibits":-1000}`)
	if err == nil || !strings.Contains(err.Error(), "credit") {
		t.Errorf("%v", err)
	}
	if _, err := manifestWith(`"capacity":{"unit":"millibits","millibits":0}`); err != nil {
		t.Errorf("a zero capacity was refused: %v", err)
	}
}

func TestACapacityInAnotherUnitIsRefused(t *testing.T) {
	// Guessing is how a capacity in bits gets debited as millibits.
	if _, err := manifestWith(`"capacity":{"unit":"bits","millibits":1}`); err == nil {
		t.Error("a capacity in bits was accepted")
	}
}

func TestAnUnknownStatusFailsTheLoad(t *testing.T) {
	raw := `{"capacity_unit":{"name":"millibits"},
		"denial_normalization":{"external_reason":"u"},
		"predicates":[{"id":"p","version":"0.1","status":"retired"}]}`
	_, err := ParsePredicateManifest([]byte(raw))
	if err == nil {
		t.Fatal("an unknown status was accepted")
	}
	if !strings.Contains(err.Error(), "retired") {
		t.Errorf("%v", err)
	}
}

func TestAMissingSchemaFieldFailsTheLoad(t *testing.T) {
	// Every other required field present, so this proves output_schema
	// specifically is required rather than proving the loop runs at all.
	raw := `{"capacity_unit":{"name":"millibits"},
		"denial_normalization":{"external_reason":"u"},
		"predicates":[{"id":"p","version":"0.1","status":"active",
		"release_shape":"boolean","sensitivity":{"class":"low"},
		"entry_digest":"sha256:aa","public_context_schema":{},
		"private_input_schema":{},"answer_domain":{},"freshness":{},
		"test_vectors":[],
		"capacity":{"unit":"millibits","millibits":1},"assurance_profiles":[],
		"provenance":{"effective_from":"2026-01-01","revoked_from":null}}]}`
	_, err := ParsePredicateManifest([]byte(raw))
	if err == nil {
		t.Fatal("an entry with no output_schema loaded")
	}
	if !strings.Contains(err.Error(), "output_schema") {
		t.Errorf("%v", err)
	}
}

func TestADuplicateKeyInTheManifestFailsTheLoad(t *testing.T) {
	// The reason this uses the package's own parser: last-wins would let a
	// publisher put the real value second.
	raw := `{"capacity_unit":{"name":"millibits"},
		"capacity_unit":{"name":"bits"},
		"denial_normalization":{"external_reason":"u"},"predicates":[]}`
	if _, err := ParsePredicateManifest([]byte(raw)); err == nil {
		t.Error("a manifest with a duplicate key loaded")
	}
}

func TestPinsRequireAKeyAndAWellFormedDigest(t *testing.T) {
	if _, err := NewRegistryPins([][32]byte{{}}, manifestEntryDigest); err != nil {
		t.Errorf("a well-formed pin was refused: %v", err)
	}
	// No key: the digest would be doing both of §4.1's jobs.
	if _, err := NewRegistryPins(nil, manifestEntryDigest); err == nil {
		t.Error("a pin set with no key was accepted")
	}
	for _, bad := range []string{
		"bd08ff230de0d8ce34de99967f7a9097988b49058f0a21dd35b9444c24098e35",
		"sha256:BD08FF230DE0D8CE34DE99967F7A9097988B49058F0A21DD35B9444C24098E35",
		"sha256:tooshort",
		"sha512:bd08ff230de0d8ce34de99967f7a9097988b49058f0a21dd35b9444c24098e35",
	} {
		if _, err := NewRegistryPins([][32]byte{{}}, bad); err == nil {
			t.Errorf("%q was accepted", bad)
		}
	}
}

func TestAKeyIsAskedAboutRatherThanListed(t *testing.T) {
	// Which publishers a custodian recognises is closer to local policy than to
	// anything a requester should learn, so the type answers a membership question
	// and does not hand the list back.
	var seven, eight [32]byte
	for i := range seven {
		seven[i], eight[i] = 7, 8
	}
	pins, err := NewRegistryPins([][32]byte{seven}, manifestEntryDigest)
	if err != nil {
		t.Fatal(err)
	}
	if !pins.AcceptsKey(seven) || pins.AcceptsKey(eight) {
		t.Error("membership is wrong")
	}
	if pins.KeyCount() != 1 {
		t.Errorf("%d keys", pins.KeyCount())
	}
}

func TestThePinnedKeyListCannotBeRewrittenByItsCaller(t *testing.T) {
	// Go-specific, and CONVENTIONS-go.md's deep-copy rule. Rust takes ownership of
	// the Vec; a Go caller retaining its slice could otherwise add a key to a
	// custodian's pin set after startup, which is the one list §4.1 says an
	// operator writes.
	var key [32]byte
	key[0] = 1
	configured := [][32]byte{key}
	pins, err := NewRegistryPins(configured, manifestEntryDigest)
	if err != nil {
		t.Fatal(err)
	}
	configured[0][0] = 2
	if pins.AcceptsKey(configured[0]) {
		t.Error("the caller rewrote a pinned key after startup")
	}
	if !pins.AcceptsKey(key) {
		t.Error("the originally pinned key is gone")
	}
}

const menuPredicate = "https://q2d.dev/predicates/dietary/menu-compatible"

func TestAKnownEntryResolvesWhenTheDeclaredDigestMatches(t *testing.T) {
	entry, err := referenceManifest(t).Resolve(menuPredicate, "0.1", manifestEntryDigest, "2026-08-31T09:00:00Z")
	if err != nil {
		t.Fatalf("did not resolve: %v", err)
	}
	if entry.ID() != menuPredicate {
		t.Errorf("resolved %q", entry.ID())
	}
}

func TestADeclaredDigestThatDiffersRejects(t *testing.T) {
	// §4.5. The failure this closes is semantic mutation without shape change: a
	// predicate edited from "is any item compatible" to "does any item conflict"
	// keeps its release shape, domain, capacity and schema, so every other check
	// passes and the answer means the opposite of what the requester believes.
	wrong := "sha256:0000000000000000000000000000000000000000000000000000000000000000"
	_, err := referenceManifest(t).Resolve(menuPredicate, "0.1", wrong, "2026-08-31T09:00:00Z")
	if err != ResolveEntryDigestMismatch {
		t.Errorf("%v, want ResolveEntryDigestMismatch", err)
	}
}

func TestAnUnknownPredicateAndAnUnknownVersionAreToldApartOnlyLocally(t *testing.T) {
	// Two internal reasons, and §4.7 makes them one wire value: telling them apart
	// on the wire would say the predicate exists, which is the custodian-private
	// policy the uniformity rule withholds.
	manifest := referenceManifest(t)
	now := "2026-08-31T09:00:00Z"
	if _, err := manifest.Resolve("https://q2d.dev/predicates/nope", "0.1", manifestEntryDigest, now); err != ResolveUnknownPredicate {
		t.Errorf("unknown id: %v", err)
	}
	if _, err := manifest.Resolve(menuPredicate, "9.9", manifestEntryDigest, now); err != ResolveUnknownVersion {
		t.Errorf("unknown version: %v", err)
	}
}

func TestAnEntryThatIsNotYetEffectiveRejects(t *testing.T) {
	// The reference entries are effective from 2026-08-03, so a now before that is
	// the case. Text comparison on the date part, which is exact.
	manifest := referenceManifest(t)
	if _, err := manifest.Resolve(menuPredicate, "0.1", manifestEntryDigest, "2026-08-02T23:59:59Z"); err != ResolveNotYetEffective {
		t.Errorf("%v, want ResolveNotYetEffective", err)
	}
	if _, err := manifest.Resolve(menuPredicate, "0.1", manifestEntryDigest, "2026-08-03T00:00:00Z"); err != nil {
		t.Errorf("the first effective day did not resolve: %v", err)
	}
}

func TestARevocationDateTakesEffectOnTheDayItself(t *testing.T) {
	// A revocation that began at the end of its own date would leave a whole day in
	// which an entry the publisher has withdrawn still answers.
	//
	// Built as a fixture rather than by editing the reference manifest, which is
	// what the first version of this test did — and the digest recomputation
	// refused it, correctly: changing revoked_from changes the entry, so the stored
	// digest no longer describes it.
	manifest, err := manifestWithRevocation(
		`"capacity":{"unit":"millibits","millibits":1}`, `"2026-09-01"`)
	if err != nil {
		t.Fatal(err)
	}
	entry, _ := manifest.EntryFor("p", "0.1")
	digest := entry.StoredEntryDigest()
	if _, err := manifest.Resolve("p", "0.1", digest, "2026-08-31T23:59:59Z"); err != nil {
		t.Errorf("the day before revocation did not resolve: %v", err)
	}
	if _, err := manifest.Resolve("p", "0.1", digest, "2026-09-01T00:00:00Z"); err != ResolveRevokedByDate {
		t.Errorf("%v, want ResolveRevokedByDate", err)
	}
}

func TestEveryResolutionFailureSharesAStepAndIsToldApartInternally(t *testing.T) {
	// §4.7's uniformity, in the half this file can assert: distinct internal
	// reasons, one step, and no wire value on the type at all — §5.2.1 makes that
	// the pinned registry's denial_normalization, which is why it is read from the
	// manifest and not from a constant.
	reasons := []ResolveError{
		ResolveUnknownPredicate, ResolveUnknownVersion, ResolveNotResolvable,
		ResolveNotYetEffective, ResolveRevokedByDate, ResolveEntryDigestMismatch,
	}
	seen := map[string]struct{}{}
	for _, r := range reasons {
		seen[r.InternalReason()] = struct{}{}
		if r.Step() != "10" {
			t.Errorf("%v at step %q", r, r.Step())
		}
	}
	if len(seen) != len(reasons) {
		t.Error("two resolution failures share an internal reason")
	}
	if referenceManifest(t).DenialNormalization() != "unavailable" {
		t.Error("the wire value does not come from the manifest")
	}
}

func TestAnEntryEditedWithoutUpdatingItsDigestIsRefused(t *testing.T) {
	// Issue 12, and only this half. Recomputation catches an entry whose stored
	// digest has gone stale — an edit someone forgot to re-digest, or a splice into
	// a manifest.
	//
	// It does not catch a publisher who edits an entry and updates its digest to
	// match: that manifest is self-consistent and recomputation agrees with it.
	// What catches that is the pin — §4.1's digest over the whole manifest, which a
	// custodian changes only after reading the diff. The test name said otherwise
	// until review pointed it out.
	raw, err := os.ReadFile("registry/manifest.json")
	if err != nil {
		t.Fatal(err)
	}
	tampered := strings.Replace(string(raw), `"release_shape": "boolean"`, `"release_shape": "enum"`, 1)
	_, err = ParsePredicateManifest([]byte(tampered))
	if err == nil {
		t.Fatal("a tampered entry loaded")
	}
	if !strings.Contains(err.Error(), "stores entry digest") {
		t.Errorf("%v", err)
	}
}

func TestAMalformedDateFailsTheLoad(t *testing.T) {
	// Resolve compares dates as text, and text comparison is exact only over
	// well-formed ones: 0000-00-00 sorts before everything and zzzz after it, so a
	// malformed date in a pinned manifest would resolve rather than fail.
	for _, bad := range []string{`"0000-00-00"`, `"zzzz"`, `"2026-02-30"`, `"2026-8-3"`} {
		_, err := manifestWithRevocation(`"capacity":{"unit":"millibits","millibits":1}`, bad)
		if err == nil || !strings.Contains(err.Error(), "YYYY-MM-DD") {
			t.Errorf("%s: %v", bad, err)
		}
	}
	if _, err := manifestWithRevocation(
		`"capacity":{"unit":"millibits","millibits":1}`, `"2026-02-29"`); err == nil {
		t.Error("2026 is not a leap year")
	}
	if _, err := manifestWithRevocation(
		`"capacity":{"unit":"millibits","millibits":1}`, `"2024-02-29"`); err != nil {
		t.Errorf("2024 is a leap year: %v", err)
	}
}
