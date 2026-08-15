package q2d

import (
	"os"
	"strings"
	"testing"
)

// The same published known answers src/digest.rs is gated on. Go's digest comes
// from crypto/sha256, so these do not guard a transcription error here — they
// guard the *pair*: if the two files ever disagree, one of these says which of
// them left the published answer.
var knownDigests = []struct{ message, expected string }{
	{"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
	{"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"},
	{
		"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
		"248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
	},
	{
		"abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmno" +
			"ijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu",
		"cf5b16a778af8380036ce59e7b0492370b249b11e8f07a51afac45037afee9d1",
	},
}

func TestDigestReproducesThePublishedKnownAnswers(t *testing.T) {
	for _, c := range knownDigests {
		if got := Digest([]byte(c.message)); got != "sha256:"+c.expected {
			t.Errorf("SHA-256 of %q:\n got  %s\n want sha256:%s", c.message, got, c.expected)
		}
	}
}

func TestADigestCarriesThePrefixAndIsLowercaseHex(t *testing.T) {
	d := Digest([]byte("abc"))
	// serialization.md §5: the prefix is mandatory so the digest is
	// self-describing.
	if !strings.HasPrefix(d, "sha256:") {
		t.Errorf("no prefix: %s", d)
	}
	// 7 + 64.
	if len(d) != 71 {
		t.Errorf("length %d: %s", len(d), d)
	}
	for _, c := range d[len("sha256:"):] {
		if !(c >= '0' && c <= '9') && !(c >= 'a' && c <= 'f') {
			t.Errorf("not lowercase hex: %s", d)
			break
		}
	}
}

func TestALeadingZeroByteKeepsItsWidth(t *testing.T) {
	// The input whose digest begins with a zero byte. Without it the
	// lowercase-hex rule is only tested where it cannot fail.
	d := Digest([]byte{0x03})
	if len(d) != 71 || !strings.HasPrefix(d, "sha256:0") {
		t.Errorf("got %s", d)
	}
}

func TestEveryFixtureDigestsToTheSharedExpectation(t *testing.T) {
	// src/digest.rs implements SHA-256 by hand because Rust's standard library
	// has none; this file uses crypto/sha256. Both are held to
	// testdata/digests.txt, which hashlib produced — so three provenances agree
	// on the same four answers, and a defect in the hand-written one shows up as
	// a disagreement with two standard libraries rather than as its own private
	// truth.
	expected, err := os.ReadFile("testdata/digests.txt")
	if err != nil {
		t.Fatalf("cannot read the digest fixture: %v", err)
	}
	checked := 0
	for _, line := range strings.Split(strings.TrimSpace(string(expected)), "\n") {
		name, want, found := strings.Cut(line, "  ")
		if !found {
			t.Fatalf("malformed fixture line: %q", line)
		}
		var bytes []byte
		if name != "<empty>" {
			if bytes, err = os.ReadFile("testdata/" + name + ".serialized"); err != nil {
				t.Fatalf("%s: %v", name, err)
			}
		}
		if got := Digest(bytes); got != want {
			t.Errorf("%s:\n got  %s\n want %s", name, got, want)
		}
		checked++
	}
	if checked != 4 {
		t.Errorf("the fixture lost a line: %d checked", checked)
	}
}
