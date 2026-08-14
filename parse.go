package q2d

// Bytes back into a Value, for payloads whose signature already verified.
//
// # What this must accept
//
// Any valid JSON the value model can hold — not only what Serialize produces.
// P-002 §4.1: producers must emit the deterministic profile; verifiers must not
// depend on it. A parser that required the profile would reject a conforming
// implementation's payload for putting a space after a colon, and would make
// verification depend on canonicalization, which is the dependency signing
// received bytes exists to remove.
//
// # What this must refuse
//
//   - Duplicate keys. §4.2 prohibits them on production and requires rejection
//     on parse. A parser taking last-wins or first-wins gives two
//     implementations two readings of one payload — and the payload is signed,
//     so both readings carry a valid signature.
//   - Floats. §4.3, and Value has no member for one.
//   - An integer outside int64. scope.md §4.1's range (E-37).
//   - Anything JSON itself refuses.
//
// # Not encoding/json
//
// The same reason writeString is hand-rolled, and a sharper one. encoding/json
// resolves duplicate keys silently by last-wins, which is exactly the rule §4.2
// requires rejecting; it decodes every number into float64, losing an int64
// above 2^53 without saying so; and it substitutes U+FFFD for invalid UTF-8.
// Three of this file's four refusals are behaviours the standard library
// deliberately does not have.
//
// # What it does not own
//
// The §4.8 limits are P-002 issue 5's, on parse_envelope. This carries one of
// them — a depth bound — because recursive descent without one is a stack
// overflow on hostile input, and verified is not trusted: a signature says who
// sent the bytes, not that they meant well.

import (
	"fmt"
	"strconv"
	"strings"
	"unicode/utf16"
	"unicode/utf8"
)

// maxDepth is P-002 §4.8's nesting bound, stated here so this parser is safe on
// its own. Issue 5 applies the full set — size, depth, and member count — at the
// envelope, before allocation.
const maxDepth = 16

// Parse reads a payload whose signature has already been verified.
//
// P-002 §5 names this parse_core and gives it a CoreObject. CoreObject does not
// exist yet, so this is the general form, exactly as Serialize is — parse_core
// becomes the typed wrapper that also checks §2.2's timestamp fields and §2's
// required ones.
//
// Taking bytes rather than a string is deliberate: a payload arrives as bytes,
// and its encoding is this function's to check rather than its caller's to
// promise.
func Parse(payload []byte) (Value, error) {
	if !utf8.Valid(payload) {
		return nil, fmt.Errorf("payload is not valid UTF-8. P-002 §4.2's profile " +
			"is UTF-8 and RFC 8259 §8.1 requires it for exchanged JSON")
	}
	p := &parser{text: string(payload)}
	p.skipWhitespace()
	value, err := p.value()
	if err != nil {
		return nil, err
	}
	p.skipWhitespace()
	if p.at != len(p.text) {
		return nil, p.fail("trailing bytes after the value")
	}
	return value, nil
}

type parser struct {
	text  string
	at    int
	depth int
}

// fail names a position and never a value: an offset is a fact about the
// input's shape, which the sender chose, where the bytes at it may be a private
// field of a response.
func (p *parser) fail(what string) error {
	return fmt.Errorf("%s, at byte %d", what, p.at)
}

func (p *parser) peek() (byte, bool) {
	if p.at >= len(p.text) {
		return 0, false
	}
	return p.text[p.at], true
}

func (p *parser) skipWhitespace() {
	// RFC 8259 §2's four, and only those. A parser that also skipped a vertical
	// tab would accept bytes another implementation rejects.
	for {
		c, ok := p.peek()
		if !ok || (c != ' ' && c != '\t' && c != '\n' && c != '\r') {
			return
		}
		p.at++
	}
}

func (p *parser) expect(want byte) error {
	if c, ok := p.peek(); ok && c == want {
		p.at++
		return nil
	}
	return p.fail(fmt.Sprintf("expected %q", string(want)))
}

func (p *parser) literal(word string, value Value) (Value, error) {
	if strings.HasPrefix(p.text[p.at:], word) {
		p.at += len(word)
		return value, nil
	}
	return nil, p.fail("not a JSON value")
}

func (p *parser) value() (Value, error) {
	c, ok := p.peek()
	if !ok {
		return nil, p.fail("input ended where a value was expected")
	}
	switch {
	case c == '{':
		return p.object()
	case c == '[':
		return p.array()
	case c == '"':
		s, err := p.string()
		if err != nil {
			return nil, err
		}
		return String(s), nil
	case c == 't':
		return p.literal("true", Bool(true))
	case c == 'f':
		return p.literal("false", Bool(false))
	case c == 'n':
		return p.literal("null", Null{})
	case c == '-' || (c >= '0' && c <= '9'):
		return p.number()
	default:
		return nil, p.fail("not a JSON value")
	}
}

func (p *parser) enter() error {
	p.depth++
	if p.depth > maxDepth {
		return p.fail(fmt.Sprintf("nested deeper than P-002 §4.8's limit of %d", maxDepth))
	}
	return nil
}

func (p *parser) object() (Value, error) {
	if err := p.expect('{'); err != nil {
		return nil, err
	}
	if err := p.enter(); err != nil {
		return nil, err
	}
	defer func() { p.depth-- }()

	pairs := Object{}
	p.skipWhitespace()
	if c, ok := p.peek(); ok && c == '}' {
		p.at++
		return pairs, nil
	}
	for {
		p.skipWhitespace()
		key, err := p.string()
		if err != nil {
			return nil, err
		}
		p.skipWhitespace()
		if err := p.expect(':'); err != nil {
			return nil, err
		}
		p.skipWhitespace()
		item, err := p.value()
		if err != nil {
			return nil, err
		}
		// §4.2: rejected on parse, not resolved. The name is repeated because
		// it is the sender's own label; nothing about the value is.
		if _, seen := pairs[key]; seen {
			return nil, p.fail(fmt.Sprintf("duplicate key %q, which P-002 §4.2 "+
				"rejects rather than resolving — two readings of one signed payload", key))
		}
		pairs[key] = item

		p.skipWhitespace()
		c, ok := p.peek()
		switch {
		case ok && c == ',':
			p.at++
		case ok && c == '}':
			p.at++
			return pairs, nil
		default:
			return nil, p.fail("expected ',' or '}'")
		}
	}
}

func (p *parser) array() (Value, error) {
	if err := p.expect('['); err != nil {
		return nil, err
	}
	if err := p.enter(); err != nil {
		return nil, err
	}
	defer func() { p.depth-- }()

	items := Array{}
	p.skipWhitespace()
	if c, ok := p.peek(); ok && c == ']' {
		p.at++
		return items, nil
	}
	for {
		p.skipWhitespace()
		item, err := p.value()
		if err != nil {
			return nil, err
		}
		items = append(items, item)

		p.skipWhitespace()
		c, ok := p.peek()
		switch {
		case ok && c == ',':
			p.at++
		case ok && c == ']':
			p.at++
			return items, nil
		default:
			return nil, p.fail("expected ',' or ']'")
		}
	}
}

func (p *parser) string() (string, error) {
	if err := p.expect('"'); err != nil {
		return "", err
	}
	var out strings.Builder
	for {
		c, ok := p.peek()
		if !ok {
			return "", p.fail("input ended inside a string")
		}
		switch {
		case c == '"':
			p.at++
			return out.String(), nil
		case c == '\\':
			p.at++
			if err := p.escape(&out); err != nil {
				return "", err
			}
		case c < 0x20:
			// RFC 8259 §7 requires it escaped, and the profile emits it
			// escaped — so accepting a raw one would admit bytes no producer
			// can make.
			return "", p.fail("unescaped control character in a string")
		default:
			// The payload is already known to be UTF-8, so this advances by
			// whole characters rather than bytes.
			r, width := utf8.DecodeRuneInString(p.text[p.at:])
			out.WriteRune(r)
			p.at += width
		}
	}
}

func (p *parser) escape(out *strings.Builder) error {
	c, ok := p.peek()
	if !ok {
		return p.fail("input ended inside an escape")
	}
	p.at++
	switch c {
	case '"', '\\', '/':
		out.WriteByte(c)
	case 'b':
		out.WriteByte('\b')
	case 'f':
		out.WriteByte('\f')
	case 'n':
		out.WriteByte('\n')
	case 'r':
		out.WriteByte('\r')
	case 't':
		out.WriteByte('\t')
	case 'u':
		return p.unicodeEscape(out)
	default:
		return p.fail("unknown escape")
	}
	return nil
}

func (p *parser) unicodeEscape(out *strings.Builder) error {
	first, err := p.hex4()
	if err != nil {
		return err
	}
	// A surrogate pair is two escapes and one character. Accepted because RFC
	// 8259 §7 describes it and a producer escaping a supplementary character
	// has no other spelling; a lone surrogate is refused, because it is not a
	// character and has no UTF-8 encoding.
	switch {
	case first >= 0xD800 && first < 0xDC00:
		if !strings.HasPrefix(p.text[p.at:], `\u`) {
			return p.fail("high surrogate with no low surrogate after it")
		}
		p.at += 2
		second, err := p.hex4()
		if err != nil {
			return err
		}
		if second < 0xDC00 || second >= 0xE000 {
			return p.fail("high surrogate followed by a non-surrogate")
		}
		out.WriteRune(utf16.DecodeRune(rune(first), rune(second)))
	case first >= 0xDC00 && first < 0xE000:
		return p.fail("low surrogate with no high surrogate before it")
	default:
		out.WriteRune(rune(first))
	}
	return nil
}

func (p *parser) hex4() (uint16, error) {
	if p.at+4 > len(p.text) {
		return 0, p.fail(`input ended inside a \u escape`)
	}
	digits := p.text[p.at : p.at+4]
	for i := 0; i < 4; i++ {
		c := digits[i]
		hex := (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')
		if !hex {
			return 0, p.fail(`\u escape is not four hex digits`)
		}
	}
	n, err := strconv.ParseUint(digits, 16, 16)
	if err != nil {
		return 0, p.fail(`\u escape is not four hex digits`)
	}
	p.at += 4
	return uint16(n), nil
}

func (p *parser) number() (Value, error) {
	start := p.at
	if c, ok := p.peek(); ok && c == '-' {
		p.at++
	}
	// RFC 8259 §6: one leading zero, or digits not starting with zero.
	c, ok := p.peek()
	switch {
	case ok && c == '0':
		p.at++
	case ok && c >= '1' && c <= '9':
		for {
			d, ok := p.peek()
			if !ok || d < '0' || d > '9' {
				break
			}
			p.at++
		}
	default:
		return nil, p.fail("a number needs a digit")
	}

	// A fraction or an exponent makes it a float syntactically, and that is the
	// test — not whether the value happens to be integral.
	//
	// 1e2 is a hundred and no conforming producer emits it; §4.2's integers
	// carry no exponent. Deciding that it is a hundred means exponent
	// arithmetic, and 1e400 means deciding in what — the float-precision
	// divergence §4.3 removes from the protocol rather than managing. A
	// syntactic test is decidable identically in every language, which is the
	// property that matters here.
	if d, ok := p.peek(); ok && (d == '.' || d == 'e' || d == 'E') {
		return nil, p.fail("a fraction or exponent, which P-002 §4.3 prohibits in a " +
			"signed structure — capacity is integer millibits, timestamps are strings")
	}

	n, err := strconv.ParseInt(p.text[start:p.at], 10, 64)
	if err != nil {
		return nil, fmt.Errorf("integer outside −2^63 … 2^63 − 1, which scope.md "+
			"§4.1 requires an entry's integers to lie within, at byte %d", start)
	}
	return Int(n), nil
}
