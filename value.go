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
	"fmt"
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
	// protocolLevel is §2.2's "the core object, routing, and a receipt": the
	// nesting at which a field name carries a core-model.md meaning. It starts
	// true and stays true only through protocolSubobjects, because a
	// public_context field called receipt is the predicate's own structure and
	// §2.6 says that may mean anything at all.
	write(b *strings.Builder, protocolLevel bool) error
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
// the typed wrapper.
//
// # Errors
//
// §4.3's float ban needs no check here — Value has no float member, so a float
// is a compile error. What remains is core-model.md §2.2's timestamp, which
// §4.2 cites: this is the last point at which a value can be refused before it
// becomes bytes somebody signs, and inside a signed payload a malformed
// timestamp is past the reach of anything that reads it as text.
//
// An error carries no private data: every message names a field or a spelling,
// both of which the caller supplied and neither of which is an answer.
func Serialize(v Value) ([]byte, error) {
	var b strings.Builder
	if err := v.write(&b, true); err != nil {
		return nil, err
	}
	return []byte(b.String()), nil
}

func (Null) write(b *strings.Builder, _ bool) error {
	b.WriteString("null")
	return nil
}

func (v Bool) write(b *strings.Builder, _ bool) error {
	if v {
		b.WriteString("true")
		return nil
	}
	b.WriteString("false")
	return nil
}

// strconv.FormatInt is exactly §4.2's integer rule: no exponent, no leading
// plus, no leading zeros. Nothing to configure and nothing two languages can
// render differently.
func (v Int) write(b *strings.Builder, _ bool) error {
	b.WriteString(strconv.FormatInt(int64(v), 10))
	return nil
}

func (v String) write(b *strings.Builder, _ bool) error {
	// By shape, at any depth: a string that has some RFC 3339 spelling but not
	// §2.2's is a malformed timestamp wherever it appears, and public_context is
	// exactly where an unexpected one would arrive.
	if looksLikeRFC3339(string(v)) && !isQ2DTimestamp(string(v)) {
		return fmt.Errorf("timestamp %q is not core-model.md §2.2's — uppercase `T`, "+
			"uppercase `Z`, second precision, and a real instant. Checking the spelling "+
			"alone would pass '2026-99-99T99:99:99Z', which has the right shape and is "+
			"no date", string(v))
	}
	writeString(string(v), b)
	return nil
}

func (v Array) write(b *strings.Builder, _ bool) error {
	b.WriteByte('[')
	for i, item := range v {
		if i > 0 {
			b.WriteByte(',')
		}
		// An array is not a protocol level of its own: §2.2 names objects, and
		// a timestamp field's value is not an array.
		if err := item.write(b, false); err != nil {
			return err
		}
	}
	b.WriteByte(']')
	return nil
}

func (v Object) write(b *strings.Builder, protocolLevel bool) error {
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
		// By name as well as by shape, so a malformed timestamp in a field
		// core-model.md gives one is caught however malformed.
		// 2026-1-01T00:00:00Z has no RFC 3339 shape at all and is still a
		// timestamp field, and so is 42.
		if protocolLevel && timestampFields[key] {
			spelling, isString := v[key].(String)
			if !isString {
				return fmt.Errorf("%s is a timestamp field and %s is not a string. "+
					"core-model.md §2.2's timestamp is one", key, typeName(v[key]))
			}
			if !isQ2DTimestamp(string(spelling)) {
				return fmt.Errorf("%s is a timestamp field and %q is not core-model.md "+
					"§2.2's timestamp — uppercase `T`, uppercase `Z`, second precision, "+
					"and a real instant", key, string(spelling))
			}
		}
		writeString(key, b)
		b.WriteByte(':')
		if err := v[key].write(b, protocolLevel && protocolSubobjects[key]); err != nil {
			return err
		}
	}
	b.WriteByte('}')
	return nil
}

// typeName gives a value's JSON type, for an error message. Never its contents
// — §4.3's sibling rule is that no private value reaches an error string.
func typeName(v Value) string {
	switch v.(type) {
	case Null:
		return "null"
	case Bool:
		return "a boolean"
	case Int:
		return "an integer"
	case String:
		return "a string"
	case Array:
		return "an array"
	case Object:
		return "an object"
	}
	return "an unknown value"
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
