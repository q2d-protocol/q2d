package q2d

// The envelope, and P-002 §4.8's limits applied where the shape allows.
//
//	{ "signed": "<JWS compact>", "routing": { … } }
//
// signed is opaque here. Its internal structure is P-003's; this layer treats it
// as a string and never inspects it — §4.4.
//
// # Where each limit lands
//
// §4 step 1 says "before any allocation on attacker-controlled data", and the
// whole-envelope bound is the one that delivers it: 64 KiB, checked on the byte
// slice before a parser is constructed. Everything after it is bounded by that,
// so the later checks are about shape rather than about exhaustion.
//
// Two of §4.8's five rows cannot be enforced at step 1, and the envelope's own
// shape is why:
//
//   - public_context — 32 KiB. It is inside the signed payload, which is
//     base64url text at this layer. Reading it here would mean decoding and
//     parsing an unverified payload, which §4's order exists to prevent: parsing
//     happens at step 5, after verification at step 4. The limit belongs to
//     parse_core, and P-002 §4.8 now says so.
//
//   - Any single string — 2 KiB. It cannot reach signed. A JWS compact of the
//     canonical query is about 1.6 KiB before any public context, so a 2 KiB cap
//     on that member would leave a few hundred bytes for the predicate's data
//     and the protocol could not carry its own worked example. signed is bounded
//     by the envelope limit; the 2 KiB applies to every other string, which here
//     means routing's.

import (
	"fmt"
	"sort"
)

// An Envelope is a parsed §4.4 envelope. Routing is optional — §2.1 makes it
// advisory, and a transport that needs no projection sends none.
type Envelope struct {
	Signed  string
	Routing Value
}

// ParseEnvelope parses an envelope under §4.8's limits.
//
// It refuses oversized input, anything Parse refuses, a missing or non-string
// signed, a non-object routing, a member that is neither, and a string in
// routing above 2 KiB.
//
// A member that is neither is refused rather than ignored: an envelope is two
// fields, and a third is either a version this build does not know or an attempt
// to have one party read what another does not. Both deny.
func ParseEnvelope(payload []byte) (Envelope, error) {
	// First, and on the slice: this is the check §4 step 1 asks for, and the
	// only one that runs before anything is allocated from the input.
	if len(payload) > MaxEnvelope {
		return Envelope{}, fmt.Errorf("envelope of %d bytes, above P-002 §4.8's "+
			"limit of %d", len(payload), MaxEnvelope)
	}

	// MaxEnvelope as the string bound, not MaxString: signed is a whole JWS
	// compact string and the envelope limit is what bounds it. Nothing is
	// unbounded — a string here cannot exceed the envelope that contains it.
	value, err := parseWithin(payload, MaxEnvelope)
	if err != nil {
		return Envelope{}, err
	}
	pairs, isObject := value.(Object)
	if !isObject {
		return Envelope{}, fmt.Errorf("an envelope is a JSON object")
	}

	var envelope Envelope
	seenSigned := false
	// Sorted, because a Go map has no order at all: an envelope with two
	// defects would otherwise be reported by whichever the runtime reached
	// first, differing between runs and from Rust, whose BTreeMap walks in
	// order. A rejection reason two implementations disagree about is a
	// divergence even when both reject.
	keys := make([]string, 0, len(pairs))
	for key := range pairs {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool { return lessUTF16(keys[i], keys[j]) })
	for _, key := range keys {
		item := pairs[key]
		switch key {
		case "signed":
			text, isString := item.(String)
			if !isString {
				return Envelope{}, fmt.Errorf("`signed` is a JWS compact string — §4.4")
			}
			envelope.Signed, seenSigned = string(text), true
		case "routing":
			if _, isObject := item.(Object); !isObject {
				return Envelope{}, fmt.Errorf("`routing` is an object of projected " +
					"fields — §4.5")
			}
			envelope.Routing = item
		default:
			// The name is the sender's own structure rather than a value, and an
			// envelope has no operation-defined members for it to be data from:
			// §4.4 gives the envelope two fields and P-003 owns what is inside
			// signed.
			return Envelope{}, fmt.Errorf("unknown envelope member %q — §4.4 has "+
				"`signed` and `routing`", key)
		}
	}
	if !seenSigned {
		return Envelope{}, fmt.Errorf("no `signed` member — §4.4")
	}

	// §4.8's 2 KiB, over the part of the envelope it can reach. Post-parse
	// rather than during, because the parser applied the envelope bound to every
	// string so that signed would fit; this narrows the rest back. Bounded work:
	// the envelope was capped before any of it was read.
	if envelope.Routing != nil {
		if longest := longestString(envelope.Routing); longest > MaxString {
			return Envelope{}, fmt.Errorf("a `routing` string of %d bytes, above "+
				"P-002 §4.8's %d", longest, MaxString)
		}
	}
	return envelope, nil
}

// longestString gives the longest string anywhere in a value, in bytes.
func longestString(value Value) int {
	longest := 0
	consider := func(n int) {
		if n > longest {
			longest = n
		}
	}
	switch typed := value.(type) {
	case String:
		consider(len(string(typed)))
	case Array:
		for _, item := range typed {
			consider(longestString(item))
		}
	case Object:
		for key, item := range typed {
			// Keys as well as values: a key is a string field of the object, and
			// a relay that read a 3 KiB member name has held it either way.
			consider(len(key))
			consider(longestString(item))
		}
	}
	return longest
}
