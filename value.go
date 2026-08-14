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
	"reflect"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
	"unicode/utf8"
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
//
// core-model.md states no integer range and deliberately does not: every integer
// the protocol defines is a count, a cardinality, or a capacity in integer
// millibits, none of which approaches a boundary. Where an integer can arrive
// from outside is registry data, and scope.md §4.1 bounds it there — an integer
// in any of an entry's schemas states minimum and maximum, both inside this
// type's range. E-37, closed as B.
//
// So int64 is not a choice this file made and the specification then followed.
// It is the width §4.1 names, chosen because it is the widest every conforming
// producer carries exactly.
type Int int64

// String is a JSON string.
type String string

// Array is a JSON array. Order is significant and preserved.
type Array []Value

// Object is a JSON object. Keys are sorted at serialization rather than stored
// in order, so P-002 §4.2's ordering rule cannot be forgotten by a caller.
type Object map[string]Value

// Serialize renders a protocol structure — a core object, a response, a
// receipt, or routing — under P-002 §4.2's deterministic production profile:
// UTF-8, no whitespace between tokens, keys ascending, integers without
// exponent or leading zeros, and minimal string escaping.
//
// For a predicate's own data, use SerializeOperationData: the bytes are the
// same and the field-name rules are not.
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
	if err := write(v, &b, true); err != nil {
		return nil, err
	}
	return []byte(b.String()), nil
}

// SerializeOperationData renders operation-defined data under the same profile.
//
// Identical bytes, and one difference in what is refused: core-model.md §2.6
// says a predicate's public_context may mean anything at all, so a field there
// called issued_at is the predicate's and not §2.2's.
//
// Two entry points rather than one, because protocol level is a property of
// what the caller is serializing and cannot be read off the nesting. Reached
// through a query, public_context is already below protocol level and its
// fields carry no §2.2 meaning; digested on its own for §4.7's
// public_context_digest it would be the root, and a single entry point would
// hold the same bytes to two different rules depending on how they were
// reached.
func SerializeOperationData(v Value) ([]byte, error) {
	var b strings.Builder
	if err := write(v, &b, false); err != nil {
		return nil, err
	}
	return []byte(b.String()), nil
}

// write dispatches, refusing the one Value the interface admits and none of the
// concrete types is: a nil interface.
//
// Calling write on it panics, and a panic is not a refusal — a serializer whose
// malformed-input path is a stack trace is not fail-closed, and this one runs
// over responses and receipts where the caller is a pipeline rather than a
// literal. The other two implementations have nothing to check: Rust's Value is
// an enum with no null-pointer state, and Python's None is the Null case.
//
// Null{} is the JSON null and is unaffected. This is the absence of a value,
// which is a different thing and not one §4.2 can render.
func write(v Value, b *strings.Builder, protocolLevel bool) error {
	if isNil(v) {
		return fmt.Errorf("a nil Value has no serialization. P-002 §4.2 renders " +
			"JSON values, and the absence of one is not null — use Null{} for that")
	}
	return v.write(b, protocolLevel)
}

// isNil reports whether v is nil, including a *typed* nil.
//
// `v == nil` catches only the zero interface. Every write method has a value
// receiver, so a pointer to one of the concrete types is also in Value's method
// set — and a nil *String is an interface holding a type and no value, which is
// not equal to nil and panics on dispatch. A serializer whose malformed-input
// path is a stack trace is not fail-closed.
//
// reflect for four lines, once per value, is the cheap half of that trade;
// performance is a Stage 8 concern (CLAUDE.md) and correctness here is not.
// Neither of the other two implementations needs this: Rust's Value is an enum
// and Python's None is the Null case.
func isNil(v Value) bool {
	if v == nil {
		return true
	}
	switch reflected := reflect.ValueOf(v); reflected.Kind() {
	case reflect.Pointer, reflect.Interface, reflect.Map, reflect.Slice, reflect.Func:
		// A nil Array or Object is *not* nil for this purpose — an Array(nil)
		// serializes as [] and an Object(nil) as {}, which is what an empty one
		// means. Only their named types reach here, and both handle nil
		// already, so this arm is for a nil pointer or a nil interface.
		if reflected.Kind() == reflect.Pointer || reflected.Kind() == reflect.Interface {
			return reflected.IsNil()
		}
		return false
	default:
		return false
	}
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

// A string is written as it is. §2.2 states its spelling for the fields it names
// — and, since E-36 closed as C, says so explicitly: "the rule reaches the
// fields this specification names, and no further". A string elsewhere is
// operation-defined data under §2.6, and whether it has one spelling is the
// predicate's entry to say, through scope.md §4.1's format: date-time.
func (v String) write(b *strings.Builder, _ bool) error {
	if err := validUTF8("string", string(v)); err != nil {
		return err
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
		if err := write(item, b, false); err != nil {
			return err
		}
	}
	b.WriteByte(']')
	return nil
}

func (v Object) write(b *strings.Builder, protocolLevel bool) error {
	keys := make([]string, 0, len(v))
	for key := range v {
		// Before sorting, not during: lessUTF16 converts to runes and would
		// substitute for a malformed key, so an invalid one would be ordered by
		// bytes it does not contain.
		if err := validUTF8("object key", key); err != nil {
			return err
		}
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
			held, isString := v[key].(String)
			if !isString {
				// typeName reports "an unknown value" for nil, which the
				// dispatch below would refuse anyway; naming the field first is
				// the more useful message.
				return fmt.Errorf("%s is a timestamp field and holds %s rather than a "+
					"string. core-model.md §2.2's timestamp is one", key, typeName(v[key]))
			}
			if !isQ2DTimestamp(string(held)) {
				// The value is not in the message. Serialize runs over responses
				// and receipts too, whose strings derive from data the requester
				// never sees, and an error is a place one of them could reach a
				// log.
				return fmt.Errorf("%s is a timestamp field and its value is not "+
					"core-model.md §2.2's timestamp — uppercase `T`, uppercase `Z`, "+
					"second precision, and a real instant", key)
			}
		}
		writeString(key, b)
		b.WriteByte(':')
		if err := write(v[key], b, protocolLevel && protocolSubobjects[key]); err != nil {
			return err
		}
	}
	b.WriteByte('}')
	return nil
}

// typeName gives a value's JSON type, for an error message. Never its contents
// — §4.3's sibling rule is that no private value reaches an error string.
func typeName(v Value) string {
	if v == nil {
		return "nothing"
	}
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

// validUTF8 refuses a string Go can hold and the profile cannot emit.
//
// §4.2 produces UTF-8. A Go string is an arbitrary byte sequence, so it can
// carry bytes that are not — and ranging over one silently substitutes U+FFFD
// for each invalid sequence, which would sign a value the caller never supplied.
//
// Rust's String cannot hold invalid UTF-8 at all, so without this the two
// implementations differ on which values exist rather than on what they produce.
// Refusing here makes the accepted set the same on both sides.
//
// The message names what was being written and nothing else. It carried the
// byte offset of the first invalid sequence until review pointed out that an
// offset is derived from the value: where a string first goes wrong is a fact
// about the string, and this runs over responses and receipts whose strings
// come from data the requester never sees. There is no "small enough" exemption
// in the rule, and a position is exactly the kind of thing that looks like one.
func validUTF8(what, s string) error {
	if utf8.ValidString(s) {
		return nil
	}
	return fmt.Errorf("%s is not valid UTF-8. P-002 §4.2 produces UTF-8, and "+
		"substituting U+FFFD would sign a value the caller did not supply", what)
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
