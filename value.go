// Package q2d is the Q2D reference implementation.
//
// A transport-neutral protocol for policy-bound, least-disclosure answers over
// data held by a participating custodian. See https://q2d.dev
//
// Nothing here is usable as a protocol yet. What exists is P-002's message
// layer, built bottom-up: the value model and the deterministic production
// serializer.
//
// # The value model, and why it has no float
//
// P-002 §4.3 prohibits floating-point in any signed structure and says a float
// reaching the serializer "is a programming error and fails loudly". A Value
// that cannot hold one fails louder: the error is a compile error, and there is
// no runtime path to test because there is no runtime path.
//
// That moves the check rather than removing it. Bytes arriving from outside can
// contain a float, and the parser is where that is refused; serialization is
// downstream of a value that already exists.
//
// The prohibition is not tidiness. IEEE-754 rendering differs between
// languages, so one float field would make two implementations emit different
// bytes for the same logical message — and the Stage 1 gate compares bytes.
//
// # Why the serializer is not a canonicalizer
//
// P-002 §4.1: producers must emit this profile; verifiers must not depend on
// it. A signature covers the exact bytes transmitted, so nothing verifies by
// re-deriving them, and a verifier that re-serialized would put a
// canonicalization dependency back into the security path — which is what
// signing received bytes exists to remove.
package q2d

import (
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
)

// A Value is anything that can appear in a signed Q2D structure: the JSON model
// minus floating-point.
//
// The concrete types are below. An interface with unexported implementations
// keeps the set closed, so a float cannot be introduced by declaring one
// elsewhere — the Go equivalent of the Rust side's enum.
type Value interface {
	write(*strings.Builder)
}

// Null is JSON null. Distinct from an absent field: P-002 §4.2 omits an absent
// optional rather than nulling it, so the two are different documents.
type Null struct{}

// Bool is JSON true or false.
type Bool bool

// Int is a JSON integer. Every numeric field in the protocol is a count, a
// cardinality, or a capacity in integer millibits (core-model.md §3.1).
type Int int64

// String is a JSON string.
type String string

// Array is a JSON array. Order is significant and preserved.
type Array []Value

// Object is a JSON object. Keys are sorted at serialization rather than stored
// in order, so P-002 §4.2's ordering rule cannot be forgotten by a caller.
type Object map[string]Value

// Serialize renders a value under P-002 §4.2's deterministic production
// profile: UTF-8, no whitespace between tokens, keys ascending, integers
// without exponent or leading zeros, and minimal string escaping.
//
// P-002 §5 names this serialize_core and gives it a CoreObject. CoreObject does
// not exist yet, and the profile is a property of the value model rather than of
// any one message type, so this is the general form and serialize_core becomes
// the typed wrapper. Total, per §4.3: there is no float to fail on.
func Serialize(v Value) []byte {
	var b strings.Builder
	v.write(&b)
	return []byte(b.String())
}

func (Null) write(b *strings.Builder) { b.WriteString("null") }

func (v Bool) write(b *strings.Builder) {
	if v {
		b.WriteString("true")
		return
	}
	b.WriteString("false")
}

// strconv.FormatInt is exactly §4.2's integer rule: no exponent, no leading
// plus, no leading zeros. Nothing to configure and nothing two languages can
// render differently.
func (v Int) write(b *strings.Builder) { b.WriteString(strconv.FormatInt(int64(v), 10)) }

func (v String) write(b *strings.Builder) { writeString(string(v), b) }

func (v Array) write(b *strings.Builder) {
	b.WriteByte('[')
	for i, item := range v {
		if i > 0 {
			b.WriteByte(',')
		}
		item.write(b)
	}
	b.WriteByte(']')
}

func (v Object) write(b *strings.Builder) {
	keys := make([]string, 0, len(v))
	for key := range v {
		keys = append(keys, key)
	}
	// §4.2 orders by UTF-16 code unit. Go's string comparison orders by byte,
	// which for UTF-8 is Unicode scalar order — the two agree for every
	// character in the BMP and disagree above it, because UTF-16 encodes a
	// supplementary character as a surrogate pair beginning at 0xD800, below
	// U+E000..U+FFFF.
	//
	// No field name in core-model.md §2 is outside ASCII, so nothing in the
	// protocol reaches the difference. It is implemented anyway, because the
	// alternative is two implementations that agree today and diverge the first
	// time a predicate registers a non-ASCII key — and that divergence would
	// look like a specification disagreement.
	sort.Slice(keys, func(i, j int) bool { return lessUTF16(keys[i], keys[j]) })
	b.WriteByte('{')
	for i, key := range keys {
		if i > 0 {
			b.WriteByte(',')
		}
		writeString(key, b)
		b.WriteByte(':')
		v[key].write(b)
	}
	b.WriteByte('}')
}

// lessUTF16 compares two strings by UTF-16 code unit, as P-002 §4.2 requires.
func lessUTF16(a, b string) bool {
	x, y := utf16.Encode([]rune(a)), utf16.Encode([]rune(b))
	for i := 0; i < len(x) && i < len(y); i++ {
		if x[i] != y[i] {
			return x[i] < y[i]
		}
	}
	return len(x) < len(y)
}

// writeString renders a JSON string under §4.2's minimal escaping rule.
//
// Escaped: what RFC 8259 §7 requires — the quote, the backslash, and the
// control characters below U+0020. Nothing else. A \uXXXX escape for a
// character that can be written directly would be a second valid encoding of
// the same string, and two producers choosing differently is the divergence
// this profile exists to prevent.
//
// Not encoding/json: it escapes <, > and & by default, which are exactly
// characters representable directly, and it would emit different bytes from the
// Rust side for any string containing one.
func writeString(s string, b *strings.Builder) {
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		// The five two-character escapes RFC 8259 names, preferred over the
		// six-character \u form for the same reason as above: one encoding of a
		// character, not two.
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		default:
			if r < 0x20 {
				b.WriteString(`\u00`)
				const hex = "0123456789abcdef"
				b.WriteByte(hex[(r>>4)&0xf])
				b.WriteByte(hex[r&0xf])
				continue
			}
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
}
