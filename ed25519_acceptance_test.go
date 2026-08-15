package q2d

import (
	"os"
	"strings"
	"testing"
)

// Both implementations are held to one acceptance table.
//
// testdata/ed25519-acceptance.txt is the file, and tests/ed25519_acceptance.rs is
// its other reader. Every row is a case where "Ed25519" alone does not decide the
// answer — RFC 8032 leaves the choice open, libraries take it differently, and
// two implementations that disagreed here would disagree about whether a message
// is authentic while both passing RFC 8032's own vectors.
//
// A two-way agreement, unlike testdata/digests.txt: the Python side signs but
// does not verify, so it cannot hold an opinion about which signatures are
// acceptable. It authored the cases instead, which is a different and weaker kind
// of independence and is worth saying rather than implying.
func TestEveryRowOfTheAcceptanceTableHolds(t *testing.T) {
	text, err := os.ReadFile("testdata/ed25519-acceptance.txt")
	if err != nil {
		t.Fatalf("testdata/ed25519-acceptance.txt: %v", err)
	}

	rows := 0
	for _, line := range strings.Split(strings.TrimSpace(string(text)), "\n") {
		fields := strings.Split(line, "  ")
		if len(fields) != 5 {
			t.Fatalf("malformed row: %q", line)
		}
		name, expected := fields[0], fields[4]
		a := mustHex(t, fields[1])
		signature := mustHex(t, fields[2])
		var message []byte
		if fields[3] != "-" {
			message = mustHex(t, fields[3])
		}

		// A key that will not decode is a rejection of the same weight: the
		// table says whether the signature is acceptable, and an unacceptable
		// key makes it unacceptable.
		accepted := false
		if key, err := NewPublicKey(a); err == nil {
			accepted = Verify(key, message, signature) == nil
		}
		if accepted != (expected == "accept") {
			t.Errorf("%s: accepted=%v, expected %s", name, accepted, expected)
		}
		rows++
	}
	// A table that failed to load would pass every assertion above.
	if rows != 10 {
		t.Errorf("the fixture lost a row: %d", rows)
	}
}
