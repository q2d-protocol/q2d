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

func manifestWith(entryPatch string) (PredicateManifest, error) {
	raw := `{"capacity_unit":{"name":"millibits"},
		"denial_normalization":{"external_reason":"unavailable"},
		"predicates":[{"id":"p","version":"0.1","status":"active",
		"release_shape":"boolean","sensitivity":{"class":"low"},
		"public_context_schema":{},"private_input_schema":{},
		"output_schema":{},"answer_domain":{},"freshness":{},
		"test_vectors":[],"assurance_profiles":["a"],
		"provenance":{"effective_from":"2026-01-01","revoked_from":null},
		"entry_digest":"sha256:aa",` + entryPatch + `}]}`
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
