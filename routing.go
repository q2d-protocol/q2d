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
// The wrapped value is unexported: §4.5's "never authored" is a property of this
// type rather than a rule a caller has to keep.
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
func (r Routing) Value() Value { return deepCopy(r.value) }

// deepCopy returns a value sharing no memory with its argument.
//
// Only Array and Object need it: the other four are immutable by construction,
// since String, Int, Bool and Null are value types with no interior state.
func deepCopy(value Value) Value {
	switch typed := value.(type) {
	case Object:
		copied := make(Object, len(typed))
		for key, item := range typed {
			copied[key] = deepCopy(item)
		}
		return copied
	case Array:
		copied := make(Array, len(typed))
		for i, item := range typed {
			copied[i] = deepCopy(item)
		}
		return copied
	default:
		return value
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
		if found, ok := at(core, path); ok {
			insert(projection, path, found)
		}
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
