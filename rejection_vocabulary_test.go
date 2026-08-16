package q2d

import (
	"os"
	"strings"
	"testing"
)

// The internal reasons this implementation produces agree with the corpus.
//
// testdata/rejection-vocabulary.txt is the corpus's own mapping, extracted by a
// Python test that fails if the file and the vectors drift apart. Every rejection
// vector names an internal reason and the wire value a requester receives, and
// both implementations have to agree on that mapping — or a vector passes in one
// and fails in the other for a reason no runner reports usefully.
//
// This covers the reasons P-003's verify sequence produces. The corpus carries
// more, from sections whose modules are not built yet; those are checked when
// they are.
func TestEveryReasonThisPackageProducesMatchesTheCorpus(t *testing.T) {
	raw, err := os.ReadFile("testdata/rejection-vocabulary.txt")
	if err != nil {
		t.Fatalf("testdata/rejection-vocabulary.txt: %v", err)
	}
	corpus := map[string][2]string{}
	for _, line := range strings.Split(strings.TrimSpace(string(raw)), "\n") {
		fields := strings.Split(line, "  ")
		if len(fields) != 3 {
			t.Fatalf("malformed row: %q", line)
		}
		corpus[fields[0]] = [2]string{fields[1], fields[2]}
	}
	if len(corpus) < 20 {
		t.Fatalf("the fixture failed to load: %d rows", len(corpus))
	}

	// The corpus's name for each constant this package can return. Written out
	// rather than derived from the constant name: the mapping is what the two
	// implementations must agree on, and deriving it here would make this test
	// agree with itself.
	ours := []struct {
		name     string
		rejected Rejected
	}{
		{"compact_segment_count", CompactSegmentCount},
		{"header_segment_not_base64url", HeaderSegmentNotBase64URL},
		{"signature_segment_not_base64url", SignatureSegmentNotBase64URL},
		{"header_member_not_permitted", HeaderMemberNotPermitted},
		{"suite_unregistered", SuiteUnregistered},
		{"signature_invalid", Unauthenticated},
		{"header_payload_suite_mismatch", HeaderPayloadSuiteMismatch},
		{"header_payload_key_mismatch", HeaderPayloadKeyMismatch},
	}

	checked := 0
	for _, c := range ours {
		expected, ok := corpus[c.name]
		if !ok {
			// A reason with no vector yet is not a failure — it is a vector this
			// section still owes, and P-003's issue rows say which.
			continue
		}
		if got := c.rejected.ExternalReason(); got != expected[0] {
			t.Errorf("%s: wire value %q, corpus says %q", c.name, got, expected[0])
		}
		if expected[1] != "-" {
			if got := c.rejected.Step(); got != expected[1] {
				t.Errorf("%s: step %q, corpus says %q", c.name, got, expected[1])
			}
		}
		checked++
	}
	// Without this the loop passes vacuously if every name is missing.
	if checked < 5 {
		t.Errorf("only %d reasons were checked against the corpus", checked)
	}
}
