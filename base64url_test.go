package q2d

import (
	"bytes"
	"strings"
	"testing"
)

// RFC 4648 §10's test vectors, in §5's alphabet and without padding. The
// published table is the standard alphabet with padding; these differ from it
// only there, and no vector in it contains a byte that maps to `+` or `/`, so
// the two agree character for character.
var rfc4648 = []struct {
	raw     string
	encoded string
}{
	{"", ""},
	{"f", "Zg"},
	{"fo", "Zm8"},
	{"foo", "Zm9v"},
	{"foob", "Zm9vYg"},
	{"fooba", "Zm9vYmE"},
	{"foobar", "Zm9vYmFy"},
}

func TestRFC4648VectorsRoundTrip(t *testing.T) {
	for _, c := range rfc4648 {
		if got := EncodeBase64URL([]byte(c.raw)); got != c.encoded {
			t.Errorf("encode(%q) = %q, want %q", c.raw, got, c.encoded)
		}
		got, err := DecodeBase64URL(c.encoded)
		if err != nil {
			t.Errorf("decode(%q): %v", c.encoded, err)
		} else if string(got) != c.raw {
			t.Errorf("decode(%q) = %q, want %q", c.encoded, got, c.raw)
		}
	}
}

func TestTheURLSafeAlphabetIsTheOneUsed(t *testing.T) {
	// 0xFB 0xFF encodes to `-_` in §5 and `+/` in §4. The one input that tells
	// the two alphabets apart, so a decoder built on the wrong one passes every
	// other test here.
	if got := EncodeBase64URL([]byte{0xfb, 0xff}); got != "-_8" {
		t.Errorf("got %q, want %q", got, "-_8")
	}
	if got, err := DecodeBase64URL("-_8"); err != nil || !bytes.Equal(got, []byte{0xfb, 0xff}) {
		t.Errorf("got %x, %v", got, err)
	}
	if _, err := DecodeBase64URL("+/8"); err == nil {
		t.Error("the standard alphabet was accepted")
	}
}

func TestPaddingIsRefused(t *testing.T) {
	for _, text := range []string{"Zg==", "Zm8="} {
		if _, err := DecodeBase64URL(text); err == nil {
			t.Errorf("%q was accepted", text)
		}
	}
	// And the message says which problem it is, because a producer hitting this
	// has a one-line fix and no way to guess it from "invalid input".
	_, err := DecodeBase64URL("Zg==")
	if !strings.Contains(err.Error(), "padding") {
		t.Errorf("message does not name padding: %v", err)
	}
}

func TestNonCanonicalTrailingBitsAreRefused(t *testing.T) {
	// `Zg` is `f`. `Zh` carries the same byte with a spare bit set, and a
	// permissive decoder returns `f` for both — one byte string, two spellings,
	// under a signature. This is the case encoding/base64 accepts.
	if got, err := DecodeBase64URL("Zg"); err != nil || string(got) != "f" {
		t.Fatalf("got %q, %v", got, err)
	}
	if _, err := DecodeBase64URL("Zh"); err == nil {
		t.Error("non-canonical trailing bits were accepted")
	}
	// Three characters: two spare bits rather than four.
	if got, err := DecodeBase64URL("Zm8"); err != nil || string(got) != "fo" {
		t.Fatalf("got %q, %v", got, err)
	}
	if _, err := DecodeBase64URL("Zm9"); err == nil {
		t.Error("non-canonical trailing bits were accepted")
	}
}

func TestAGroupOfOneCharacterIsRefused(t *testing.T) {
	for _, text := range []string{"Z", "Zm9vZ"} {
		if _, err := DecodeBase64URL(text); err == nil {
			t.Errorf("%q was accepted", text)
		}
	}
}

func TestWhitespaceIsNotIgnored(t *testing.T) {
	// MIME base64 wraps at 76 columns and decoders often skip whitespace. A JWS
	// segment has none, and skipping it would accept a compact string that is
	// not the one that was signed.
	for _, text := range []string{"Zm9v YmFy", "Zm9v\nYmFy", " Zm9v"} {
		if _, err := DecodeBase64URL(text); err == nil {
			t.Errorf("%q was accepted", text)
		}
	}
}

func TestEveryByteRoundTrips(t *testing.T) {
	// Exhaustive over single bytes and over the 65 536 two-byte strings: the
	// encoder's shift arithmetic is where an off-by-one lives, and these are the
	// lengths whose final group is short.
	for a := 0; a < 256; a++ {
		one := []byte{byte(a)}
		if got, err := DecodeBase64URL(EncodeBase64URL(one)); err != nil || !bytes.Equal(got, one) {
			t.Fatalf("%x: %x, %v", one, got, err)
		}
		for b := 0; b < 256; b++ {
			two := []byte{byte(a), byte(b)}
			if got, err := DecodeBase64URL(EncodeBase64URL(two)); err != nil || !bytes.Equal(got, two) {
				t.Fatalf("%x: %x, %v", two, got, err)
			}
		}
	}
}

func TestNothingEncodableIsRefusedByTheDecoder(t *testing.T) {
	// The canonicalization check must not reject the encoder's own output. A
	// stricter-than-intended rule would show up here rather than as a
	// verification failure three modules away.
	for length := 0; length < 64; length++ {
		raw := make([]byte, length)
		for i := range raw {
			raw[i] = byte(i*37 + 11)
		}
		if got, err := DecodeBase64URL(EncodeBase64URL(raw)); err != nil || !bytes.Equal(got, raw) {
			t.Fatalf("length %d: %x, %v", length, got, err)
		}
	}
}

func TestNoErrorMessageCarriesDecodedContent(t *testing.T) {
	// §5.2's rule reaches here: the input is a payload segment, and a message
	// naming the offending character would put one byte of it in a log.
	for _, bad := range []string{"Zg==", "+/8", "Z", "Zh", "Zm9v YmFy", "Zm9vé"} {
		_, err := DecodeBase64URL(bad)
		if err == nil {
			t.Fatalf("%q was accepted", bad)
		}
		for _, c := range bad {
			for _, quoted := range []string{"'" + string(c) + "'", "\"" + string(c) + "\""} {
				if strings.Contains(err.Error(), quoted) {
					t.Errorf("%q: message carries input: %v", bad, err)
				}
			}
		}
	}
}
