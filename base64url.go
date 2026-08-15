// Base64url without padding — RFC 4648 §5 as RFC 7515 §2 uses it.
//
// Every segment of a JWS compact string is encoded this way, so this sits under
// everything P-003 signs and verifies.
//
// # What it refuses, and why refusing matters here
//
// A decoder that accepts more than one spelling of the same bytes is a
// malleability surface, and one segment of a compact JWS is exposed to it.
//
// Re-spelling the header or the payload changes the signing input, so a
// permissive decoder gains an attacker nothing there — verification fails on its
// own. The signature segment is the exception: it is not an input to anything, so
// a second spelling of the same 64 bytes verifies exactly as the first does,
// while the signed string differs. request_digest is taken over the exact signed
// bytes (core-model.md §6), so that is one exchange with two digests, and a
// receipt that no longer matches the message anyone holds.
//
// suite/verify/respelled-signature-segment is that case as a shared vector.
//
// So three refusals, none of them optional:
//
//   - Padding. `=` is not in the encoding RFC 7515 §2 specifies. Accepting it
//     would make AAAA and AAAA= the same message.
//   - The standard alphabet. `+` and `/` are RFC 4648 §4's, not §5's.
//   - Non-canonical trailing bits. A final group of two characters carries one
//     byte and four spare bits; of three characters, two bytes and two spare.
//     The spare bits must be zero. QQ and QR both decode to `A` under a
//     permissive decoder, and that is the malleability above in its smallest
//     form.
//
// A final group of one character is impossible: six bits cannot be a byte.
// Rejected as a length error rather than silently dropped.
//
// # Not encoding/base64
//
// base64.RawURLEncoding is the right alphabet and the right padding, and it
// accepts non-canonical trailing bits — Go's decoder does not check them, which
// is documented behaviour and correct for RFC 4648, whose §3.5 makes the check
// optional. It is not optional under a signature. Hand-written for that one
// reason, and the trailing-bit check in DecodeBase64URL is the whole of the
// difference.
package q2d

import (
	"fmt"
	"strings"
)

// alphabet is RFC 4648 §5's, in value order.
const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

// EncodeBase64URL encodes bytes as unpadded base64url.
func EncodeBase64URL(raw []byte) string {
	var b strings.Builder
	b.Grow((len(raw) + 2) / 3 * 4)
	for i := 0; i < len(raw); i += 3 {
		chunk := raw[i:min(i+3, len(raw))]
		var bits uint32
		for j := 0; j < 3; j++ {
			if j < len(chunk) {
				bits |= uint32(chunk[j]) << (16 - 8*j)
			}
		}
		// One output character per six bits, and one fewer group for each byte
		// the final chunk is short: 3 bytes → 4 characters, 2 → 3, 1 → 2.
		for j := 0; j <= len(chunk); j++ {
			b.WriteByte(alphabet[(bits>>(18-6*j))&0x3f])
		}
	}
	return b.String()
}

// DecodeBase64URL decodes unpadded base64url, refusing every other spelling of
// the same bytes.
func DecodeBase64URL(text string) ([]byte, error) {
	if len(text)%4 == 1 {
		// Six bits is not a byte and never was a byte. A decoder that dropped
		// this group would accept a string no encoder can produce.
		return nil, fmt.Errorf("%d characters: a base64url group of one "+
			"character encodes nothing", len(text))
	}

	out := make([]byte, 0, len(text)/4*3)
	for i := 0; i < len(text); i += 4 {
		chunk := text[i:min(i+4, len(text))]
		var bits uint32
		for j := 0; j < len(chunk); j++ {
			v := strings.IndexByte(alphabet, chunk[j])
			if v < 0 {
				return nil, badCharacter(chunk[j])
			}
			bits |= uint32(v) << (18 - 6*j)
		}
		// 4 characters → 3 bytes, 3 → 2, 2 → 1.
		for j := 0; j < len(chunk)-1; j++ {
			out = append(out, byte(bits>>(16-8*j)))
		}
		// Whatever the emitted bytes did not consume must have been zero. A
		// non-zero remainder is a second spelling of the bytes above it.
		//
		// The mask covers every bit below the last emitted byte; the bits below
		// the group itself are structurally zero, so it is the same test. The
		// count is not the mask width — a group of two characters holds twelve
		// bits and emits eight, so four are spare, and a group of three holds
		// eighteen and emits sixteen.
		if unconsumed := 8 * (4 - len(chunk)); unconsumed > 0 && bits&(1<<unconsumed-1) != 0 {
			spare := 6*len(chunk) - 8*(len(chunk)-1)
			return nil, fmt.Errorf("%d trailing bits that are not zero, which "+
				"is a second spelling of the same bytes", spare)
		}
	}
	return out, nil
}

// badCharacter names the problem and never the character: the input may be a
// payload segment, and core-model.md §5.2 keeps values out of error text.
func badCharacter(c byte) error {
	switch c {
	case '=':
		return fmt.Errorf("padding, which RFC 7515 §2's encoding does not use " +
			"— `AAAA` and `AAAA=` would otherwise be one message with two " +
			"spellings")
	case '+', '/':
		return fmt.Errorf("a character from RFC 4648 §4's standard alphabet; " +
			"§5's URL-safe alphabet uses `-` and `_`")
	default:
		return fmt.Errorf("a character outside RFC 4648 §5's alphabet")
	}
}
