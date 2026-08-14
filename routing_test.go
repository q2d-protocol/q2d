package q2d

import (
	"strings"
	"testing"
)

// These mirror src/routing.rs's tests case for case.

func routingQuery() Value {
	return Object{
		"q2d_version": String("0.1"),
		"type":        String("query"),
		"issued_at":   String("2026-07-31T09:00:00Z"),
		"expires_at":  String("2026-07-31T09:05:00Z"),
		"nonce":       String("Ux7kFQ2mS0aVvJ1cPzN4bw"),
		"target": Object{
			"custodian": String("https://friend.example/.well-known/q2d"),
			"subjects":  Array{String("did:key:z6MkSubject")},
		},
		"predicate": Object{
			"id":             String("https://q2d.dev/predicates/dietary/menu-compatible"),
			"version":        String("0.1"),
			"public_context": Object{"menu": String("risotto-contains-milk")},
		},
		"purpose":         Object{"code": String("social.meal-planning")},
		"delivery":        Object{"answer_recipient": String("did:key:z6MkRuntime")},
		"answer_contract": Object{"release_shape": String("boolean")},
	}
}

func routingText(t *testing.T, r Routing) string {
	t.Helper()
	bytes, err := Serialize(r.Value())
	if err != nil {
		t.Fatalf("serializing a projection: %v", err)
	}
	return string(bytes)
}

func TestItProjectsTheSixFieldsAndTheirShape(t *testing.T) {
	want := `{"expires_at":"2026-07-31T09:05:00Z","predicate":{"id":"https://q2d.dev/predicates/dietary/menu-compatible","version":"0.1"},"q2d_version":"0.1","target":{"custodian":"https://friend.example/.well-known/q2d"},"type":"query"}`
	if got := routingText(t, ProjectRouting(routingQuery())); got != want {
		t.Errorf("got  %s\nwant %s", got, want)
	}
}

func TestNothingTheProtocolExistsToBoundIsProjected(t *testing.T) {
	// The rule that matters most in this file: anything projected travels in
	// the clear. Asserted on the serialized bytes rather than the structure,
	// because a relay reads bytes.
	//
	// Not "menu" on its own: predicate.id is .../menu-compatible, which is
	// projected and legitimately contains it. A substring test over serialized
	// bytes has to pick markers that cannot collide with a field it is not
	// about, and this one collided on the first run.
	got := routingText(t, ProjectRouting(routingQuery()))
	for _, withheld := range []string{
		"purpose", "delivery", "answer_contract", "subjects", "public_context",
		// And their values, in case a future projection carried one under a
		// different name.
		"social.meal-planning", "did:key:z6MkRuntime", "did:key:z6MkSubject",
		"boolean", "risotto-contains-milk",
		// Two fields §2.2 marks required and §4.5 does not project.
		"issued_at", "nonce",
	} {
		if strings.Contains(got, withheld) {
			t.Errorf("%s reached routing", withheld)
		}
	}
}

func TestProjectionIsTotal(t *testing.T) {
	// §4.5's acceptance. A core object missing every projected field, one that
	// is not an object at all, and one whose target is a string rather than an
	// object — none an error, all a strict subset.
	for _, c := range []struct {
		core Value
		want string
	}{
		{Object{"nonce": String("x")}, "{}"},
		{Null{}, "{}"},
		{Array{}, "{}"},
		{Object{"target": String("not an object"), "type": String("query")}, `{"type":"query"}`},
	} {
		if got := routingText(t, ProjectRouting(c.core)); got != c.want {
			t.Errorf("got %s, want %s", got, c.want)
		}
	}
}

func TestAPartialCoreObjectProjectsAPartialRouting(t *testing.T) {
	// Absent rather than defaulted. A projection that substituted an empty
	// string for a missing custodian would introduce a field §2.1 says it may
	// never introduce, and §4.6 would then compare a value nothing signed.
	partial := Object{"type": String("query"), "predicate": Object{"id": String("p")}}
	if got := routingText(t, ProjectRouting(partial)); got != `{"predicate":{"id":"p"},"type":"query"}` {
		t.Errorf("got %s", got)
	}
}

func TestEveryKeyItWritesWasReadFromTheCoreObject(t *testing.T) {
	// §2.1: routing may never introduce a field. Stated as a property over the
	// projection rather than as a list, so it holds for whatever `projected`
	// becomes.
	if !subsetOf(ProjectRouting(routingQuery()).Value(), routingQuery()) {
		t.Error("the projection introduced a field")
	}
}

// subsetOf reports whether every key in projection, at every depth, exists in
// core with the same value at a leaf.
func subsetOf(projection, core Value) bool {
	projected, isObject := projection.(Object)
	signed, coreIsObject := core.(Object)
	if !isObject || !coreIsObject {
		a, errA := Serialize(projection)
		b, errB := Serialize(core)
		return errA == nil && errB == nil && string(a) == string(b)
	}
	for key, value := range projected {
		found, present := signed[key]
		if !present || !subsetOf(value, found) {
			return false
		}
	}
	return true
}

func TestTheProjectionOfAProjectionIsItself(t *testing.T) {
	// Idempotence, which is what makes "derived, never authored" checkable by
	// the far end: a relay that re-derived from what it received would get the
	// same bytes, so the §4.6 comparison has one fixed point.
	once := ProjectRouting(routingQuery())
	twice := ProjectRouting(once.Value())
	if routingText(t, once) != routingText(t, twice) {
		t.Errorf("not idempotent:\n once: %s\n twice: %s",
			routingText(t, once), routingText(t, twice))
	}
}

func TestAReadProjectionCannotBeMutatedBackIntoTheRouting(t *testing.T) {
	// Object is a map, so returning the stored value would hand a caller the
	// projection's own memory — and authoring a routing field is exactly what
	// this type exists to prevent. Rust's as_value is an immutable borrow;
	// Go has to copy, and this is the test that says it does.
	routing := ProjectRouting(routingQuery())
	before := routingText(t, routing)

	read := routing.Value().(Object)
	read["purpose"] = String("social.meal-planning")
	read["target"].(Object)["custodian"] = String("https://attacker.example")
	delete(read, "type")

	if after := routingText(t, routing); after != before {
		t.Errorf("mutating a read projection changed the routing\n before: %s\n after:  %s",
			before, after)
	}
	// The nested mutation is the one a shallow copy would miss.
	if !strings.Contains(before, "friend.example") {
		t.Fatal("the fixture no longer exercises the nested case")
	}
}
