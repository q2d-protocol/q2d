package q2d

// The routing projection: derived from a core object, never authored.
//
// P-002 §4.5. A producer that sends routing derives it by projection; it never
// constructs one independently. Hand-authoring makes producer-side disagreement
// possible — two fields built from two code paths that can drift — where
// deriving makes core-model.md §2.1's strict-subset property structurally true
// and leaves the §4.6 check exactly one job: detecting tampering in transit.
//
// # What is projected, and what never is
//
// q2d_version, type, target.custodian, predicate.id, predicate.version,
// expires_at — each because a relay needs it to dispatch or capability-match
// without unwrapping.
//
// Never purpose, delivery, answer_contract, target.subjects, or public_context.
// Anything projected travels in the clear, and those are what the protocol
// exists to bound. The list is closed: adding to it is a disclosure decision
// rather than a plumbing one, and an escalation (§9.4).
//
// # Why this type has no other constructor
//
// Routing wraps a value whose only origin is ProjectRouting. The field is
// unexported, so nothing outside this package can build one from whatever it
// likes, and §4.5's rule is enforced by the type rather than remembered by a
// caller.
//
// The limit is honest and P-002 §8's last row states it: code *in this package*
// could still construct one, and an implementation determined to route around
// the interface can. What the type removes is the accident — the code path that
// assembles a projection by hand because it was convenient, drifts from this
// one, and produces an envelope that fails §4.6 at the far end for no
// attacker's benefit.
//
// A routing that arrived from the wire is not this type. That one is a Value
// and stays one: it is a claim, not a derivation, and issue 7's check_routing is
// what compares the two.

import (
	"fmt"
	"sort"
	"strings"
)

// projected is the fields §4.5 projects, as paths into the core object.
//
// Paths rather than names because three of them are nested, and flattening them
// into custodian and id would lose which object they came from — which is
// exactly what §4.6 has to compare them against.
var projected = [][]string{
	{"q2d_version"},
	{"type"},
	{"target", "custodian"},
	{"predicate", "id"},
	{"predicate", "version"},
	{"expires_at"},
}

// A Routing is a projection of a core object, derived by ProjectRouting.
//
// The wrapped value is unexported, so a caller cannot choose what is in one:
// §4.5's "never authored" is a property of this type rather than a rule a caller
// has to keep.
//
// Go admits `q2d.Routing{}` where Rust's private tuple field does not, and that
// is harmless rather than a hole — **the zero value is the projection of
// nothing**, which is what Value returns for it. An empty projection is a legal
// strict subset (§2.1) and the same thing ProjectRouting gives for a core object
// with no projected field, so the invariant holds for every Routing that can be
// constructed: its fields, if any, came from a core object.
type Routing struct {
	value Value
}

// Value gives the projection for serializing into an envelope.
//
// A **copy**, and that is the whole of it: Object is a map, so returning the
// stored value would hand a caller the projection's own memory, and
// `r.Value().(q2d.Object)["purpose"] = …` would author a routing field through
// an API whose entire purpose is that they cannot. Rust's `as_value` is an
// immutable borrow and gets this from the type system; Go has to copy.
//
// There is no constructor going the other way either: a caller can read a
// projection and cannot mint one. What neither language prevents is a caller
// building its own Value and serializing that into an envelope by hand — §8's
// last row says so. The copy removes the accident, not the determined bypass.
func (r Routing) Value() Value {
	if r.value == nil {
		// The zero value, which a caller can write and which projects nothing.
		return Object{}
	}
	// The `ok` is discarded because it cannot be false: ProjectRouting stores
	// only what it could copy, so everything here is already concrete.
	copied, _ := deepCopy(r.value)
	return copied
}

// deepCopy returns a value sharing no memory with its argument, and whether
// everything in it was one of the six concrete types.
//
// The second return is what keeps a Routing serializable. `concrete` in
// value.go closes the set at the *dispatcher*, which stops a pointer reaching
// the wire; it does not stop one being *stored*, and a top-level check does not
// see `Object{"type": Object{"x": &obj}}`. A projection holding a value
// Serialize refuses is a Routing that cannot be used, which is a worse thing to
// hand a caller than a projection that left the field out.
//
// Only Array and Object need copying: the other four are value types with no
// interior state, so String, Int, Bool and Null are already immutable.
func deepCopy(value Value) (Value, bool) {
	switch typed := value.(type) {
	case Object:
		copied := make(Object, len(typed))
		for key, item := range typed {
			item, ok := deepCopy(item)
			if !ok {
				return nil, false
			}
			copied[key] = item
		}
		return copied, true
	case Array:
		copied := make(Array, len(typed))
		for i, item := range typed {
			item, ok := deepCopy(item)
			if !ok {
				return nil, false
			}
			copied[i] = item
		}
		return copied, true
	case Null, Bool, Int, String:
		return value, true
	default:
		// A pointer to one of the six, a typed nil, or anything else the
		// interface admits and the profile cannot render.
		return nil, false
	}
}

// ProjectRouting derives routing from a core object.
//
// Total. A core object missing a projected field simply does not project it,
// which is the behaviour §2.1 and §4.6 already describe: routing is a strict
// subset, and the consistency check compares each field present in it. There is
// nothing here to fail on, so there is no error path for a caller to handle
// wrongly, and no temptation to substitute a default for a field that was not
// there.
//
// It follows that this cannot introduce a field, which is §2.1's other rule:
// every key it writes was read from the core object one line earlier.
func ProjectRouting(core Value) Routing {
	projection := Object{}
	for _, path := range projected {
		found, present := at(core, path)
		if !present {
			continue
		}
		// Copied on the way in as well as on the way out. Rust clones the value
		// here; without this, a projected leaf that is itself an Object or
		// Array — reachable with malformed-but-representable input, since this
		// function is total and does not require `type` to be a string — would
		// alias the caller's core object, and mutating that afterwards would
		// mutate a derived projection.
		//
		// A field the copy refuses is **left out** rather than raising: this
		// function is total, and a projection missing a field is a strict
		// subset, which §2.1 permits and §4.6 handles. Storing it instead would
		// give the caller a Routing that Serialize will not accept.
		copied, ok := deepCopy(found)
		if !ok {
			continue
		}
		insert(projection, path, copied)
	}
	return Routing{value: projection}
}

// at gives the value at a path, if the path exists and every step is an object.
func at(value Value, path []string) (Value, bool) {
	here := value
	for _, step := range path {
		pairs, isObject := here.(Object)
		if !isObject {
			return nil, false
		}
		next, present := pairs[step]
		if !present {
			return nil, false
		}
		here = next
	}
	return here, true
}

// insert writes a value at a path, creating the objects along the way.
func insert(into Object, path []string, value Value) {
	here := into
	for _, step := range path[:len(path)-1] {
		next, present := here[step]
		if !present {
			created := Object{}
			here[step] = created
			here = created
			continue
		}
		pairs, isObject := next.(Object)
		if !isObject {
			// Unreachable: every parent this walk creates is an object. A
			// return rather than a panic because a projection that gave up on
			// one field is still a strict subset, where a panic in a producer
			// is an outage.
			return
		}
		here = pairs
	}
	here[path[len(path)-1]] = value
}

// A RoutingMismatch is a routing projection that disagrees with the verified
// core object.
//
// The internal reason. core-model.md §5.2.1 gives routing_mismatch as an
// external value too, and the two coinciding is not a licence to use one
// variable for both: P-009 builds the wire response, and this type is what a
// responder logs. Carrying the path is the whole reason it exists — an operator
// needs to know which field was tampered with, and a requester must not be told.
type RoutingMismatch struct {
	// Path is the path in routing that disagreed, as target.custodian.
	Path string
	// Because is why, in one of two ways, and never with either value: the
	// projection is attacker-supplied and the core object is the requester's.
	Because Because
}

// A Because is one of the two internal reasons a projection is rejected.
//
// The names are the corpus's, not this file's:
// conformance/corpus/message/routing/ already distinguishes them, and a third
// vocabulary for the same two facts is how a runner comes to report something no
// vector asserts. Both normalize to §5.2.1's external routing_mismatch, which is
// P-009's to emit.
type Because int

const (
	// RoutingSignedMismatch — the field holds something else in the verified
	// object, or is not there at all. §4 step 8's tampering.
	RoutingSignedMismatch Because = iota
	// RoutingIntroducedField — the field is not one §4.5 projects, and §2.1
	// says routing "carries at most" those six.
	//
	// Refused however faithful the copy, which is the rule the corpus vector
	// exists to pin: its purpose is byte-identical to the signed one, so
	// agreement is not what fails. The harm is the projection rather than the
	// mismatch — a projected field is legible without decoding signed, so it is
	// the one infrastructure indexes and retains, and a relay that copies
	// purpose up from the payload has made it cheap to harvest while changing
	// nothing.
	RoutingIntroducedField
)

func (m RoutingMismatch) Error() string {
	because := "disagrees with the signed object"
	if m.Because == RoutingIntroducedField {
		because = "is not a field §4.5 projects"
	}
	return fmt.Sprintf("`routing.%s` %s — core-model.md §4 step 8", m.Path, because)
}

// CheckRouting compares a received routing against the verified core object.
//
// core-model.md §4 step 8, after verification and parse. For each field present
// in routing, the same path must exist in the core object and hold the same
// value — exactly, with no coercion: same type, same value, and for a string
// the same characters. Any difference is tampering: reject, do not reconcile.
//
// # This reads nothing from routing
//
// It compares and returns a verdict. The projection is unauthenticated until
// this passes and is not authoritative afterwards either — §2.1 forbids using
// it for any decision the signature covers, and the way to keep that true is
// for no value to leave here.
//
// # Objects recurse, everything else is exact
//
// A projection carrying target: {custodian: …} is a subset of a core object
// whose target also has subjects, so an object is compared field by field. A
// leaf, an array, or a type mismatch is compared whole: §4.4 makes array order
// significant, and a subset rule for arrays would let a relay drop an element
// and call it a projection.
//
// # An absent projection is not a disagreement
//
// A nil routing passes. §2.1 permits a message with no projection at all
// (E-38), and nothing that is not there can disagree with anything.
func CheckRouting(core Value, routing Value) error {
	if routing == nil {
		return nil
	}
	// Against the projection of the core object, not against the core object
	// itself.
	//
	// Both were tried. Comparing against the core object means enumerating what
	// routing may not contain — a field outside the allowlist, a key that looks
	// like a nested path, a value that differs — and review found three of those
	// one at a time, which is the shape of a wrong model rather than three bugs.
	// §4.5 already says exactly what a projection may hold, and it says it by
	// construction: ProjectRouting is total, so every core object has one, and
	// "is this a subset of that" answers all three questions at once.
	return compareRouting(ProjectRouting(core).Value(), routing, nil)
}

// equalValues reports whether two values are the same: same type, same value,
// and for a string the same characters — §4 step 8's comparison, with no
// coercion. An Int never equals a String that spells it.
//
// Rust gets this from `#[derive(PartialEq)]` on a closed enum. Go has to write
// it out, and writing it out is what keeps the two agreeing: the obvious
// shortcut, comparing serialized bytes, silently imports the serializer's
// validation into a comparison.
func equalValues(a, b Value) bool {
	switch left := a.(type) {
	case Null:
		_, ok := b.(Null)
		return ok
	case Bool:
		right, ok := b.(Bool)
		return ok && left == right
	case Int:
		right, ok := b.(Int)
		return ok && left == right
	case String:
		right, ok := b.(String)
		return ok && left == right
	case Array:
		right, ok := b.(Array)
		if !ok || len(left) != len(right) {
			return false
		}
		for i := range left {
			if !equalValues(left[i], right[i]) {
				return false
			}
		}
		return true
	case Object:
		right, ok := b.(Object)
		if !ok || len(left) != len(right) {
			return false
		}
		for key, value := range left {
			found, present := right[key]
			if !present || !equalValues(value, found) {
				return false
			}
		}
		return true
	default:
		// Not one of the six. Never equal to anything, including itself: the
		// profile cannot render it, so no comparison over it is meaningful.
		return false
	}
}

// shown renders a path as target.custodian, for a message. Only ever for a
// message: the comparison walks segments, because a key may contain a dot.
func shown(path []string) string {
	if len(path) == 0 {
		return "<root>"
	}
	return strings.Join(path, ".")
}

func compareRouting(derived, routing Value, path []string) error {
	// Both objects: routing may carry a subset of the fields, so descend.
	signed, derivedIsObject := derived.(Object)
	projected, routingIsObject := routing.(Object)
	if derivedIsObject && routingIsObject {
		// Sorted, so an envelope with two disagreeing fields names the same one
		// in both implementations — a rejection reason they differ on is a
		// divergence even when both reject.
		keys := make([]string, 0, len(projected))
		for key := range projected {
			keys = append(keys, key)
		}
		sort.Slice(keys, func(i, j int) bool { return lessUTF16(keys[i], keys[j]) })

		for _, key := range keys {
			here := append(path, key)
			found, present := signed[key]
			if !present {
				// Not in the projection, and that is the whole test: §4.5 says
				// what a projection holds, so a field the derivation did not
				// produce was introduced — whether the core object has it
				// elsewhere (a faithful purpose, the corpus's own case) or
				// nowhere at all.
				return RoutingMismatch{Path: shown(here), Because: RoutingIntroducedField}
			}
			if err := compareRouting(found, projected[key], here); err != nil {
				return err
			}
		}
		return nil
	}

	// Anything else: equal or it is tampering.
	//
	// Structural, not serialized. Comparing bytes would run the profile's
	// *validation* as a side effect — Serialize refuses a malformed §2.2
	// timestamp — so `expires_at: "not a date"` present identically in both
	// would be a step-8 mismatch here and equal in Rust, whose `==` is
	// structural. Step 8 asks whether two values agree, not whether either is
	// well formed; a malformed one is refused at the step that owns it.
	if equalValues(derived, routing) {
		return nil
	}
	return RoutingMismatch{Path: shown(path), Because: RoutingSignedMismatch}
}
