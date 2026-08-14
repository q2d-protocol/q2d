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

func TestMutatingTheCoreAfterwardsDoesNotChangeTheProjection(t *testing.T) {
	// The other half of the aliasing question. A projected leaf is normally a
	// String, which is immutable — but this function is total and does not
	// require `type` to be one, so a malformed-but-representable core object
	// can put an Object at a projected path.
	//
	// Rust clones the value; Go copies it, and this is the test that says so.
	core := Object{
		"type":   Object{"smuggled": String("original")},
		"target": Object{"custodian": String("https://friend.example")},
	}
	routing := ProjectRouting(core)
	before := routingText(t, routing)

	core["type"].(Object)["smuggled"] = String("mutated")
	core["target"].(Object)["custodian"] = String("https://attacker.example")

	if after := routingText(t, routing); after != before {
		t.Errorf("mutating the core changed a derived projection\n before: %s\n after:  %s",
			before, after)
	}
}

func TestTheZeroRoutingIsTheProjectionOfNothing(t *testing.T) {
	// Go admits q2d.Routing{} where Rust's private tuple field does not. That
	// is harmless rather than a hole: the zero value carries no fields, so the
	// most a caller gets by writing one is an empty projection — a legal strict
	// subset under §2.1, and the same thing ProjectRouting gives for a core
	// object with nothing to project.
	//
	// What a caller still cannot do is choose what is in one, which is the
	// property §4.5 asks for.
	if got := routingText(t, Routing{}); got != "{}" {
		t.Errorf("the zero value: %s", got)
	}
	if got := routingText(t, ProjectRouting(Object{"nonce": String("x")})); got != "{}" {
		t.Errorf("a core object with nothing to project: %s", got)
	}
}

func TestAValueOutsideTheSixIsNotProjected(t *testing.T) {
	// concrete() in value.go closes the set at the dispatcher, which stops a
	// pointer reaching the wire. It does not stop one being stored, and a
	// top-level check does not see one nested inside a projected object.
	//
	// A projection holding a value Serialize refuses is a Routing that cannot
	// be used, which is worse to hand a caller than one that left the field
	// out — and leaving it out is what totality already means.
	inner := Object{"x": Int(1)}
	text := String("query")
	core := Object{
		"type":        &text,                             // a pointer at a leaf
		"predicate":   Object{"id": Object{"n": &inner}}, // and one nested inside
		"q2d_version": String("0.1"),                     // and a field that is fine
	}
	got := routingText(t, ProjectRouting(core))
	if got != `{"q2d_version":"0.1"}` {
		t.Errorf("got %s, want only the concrete field", got)
	}
}

func TestADerivedProjectionAgreesWithItsOwnCoreObject(t *testing.T) {
	// The property that makes the check meaningful: if projection and
	// comparison disagreed about the same message, every conforming exchange
	// would fail step 8.
	core := routingQuery()
	if err := CheckRouting(core, ProjectRouting(core).Value()); err != nil {
		t.Errorf("a derived projection disagreed with its own core object: %v", err)
	}
}

func TestAnAbsentProjectionIsNotADisagreement(t *testing.T) {
	// §2.1 permits a message with no projection (E-38), and nothing that is not
	// there can disagree with anything.
	if err := CheckRouting(routingQuery(), nil); err != nil {
		t.Errorf("absent: %v", err)
	}
	// Nor is an empty one, which is a projection of nothing.
	if err := CheckRouting(routingQuery(), Object{}); err != nil {
		t.Errorf("empty: %v", err)
	}
}

func TestAChangedValueIsTampering(t *testing.T) {
	// message/routing/disagrees in miniature: a relay rewrites the custodian so
	// the request reaches it instead.
	tampered := Object{"target": Object{"custodian": String("https://attacker.example")}}
	err := CheckRouting(routingQuery(), tampered)
	mismatch, isMismatch := err.(RoutingMismatch)
	if !isMismatch {
		t.Fatalf("expected a RoutingMismatch, got %v", err)
	}
	if mismatch.Path != "target.custodian" || mismatch.Because != RoutingSignedMismatch {
		t.Errorf("got %+v", mismatch)
	}
}

func TestAFieldOutsideTheAllowlistIsRefusedHoweverFaithfulTheCopy(t *testing.T) {
	// message/routing/introduces-field, whose purpose is byte-identical to the
	// signed one — so agreement is not what fails. §2.1 says routing carries at
	// most six fields, and this check accepted that vector until review caught
	// it.
	core := routingQuery()
	faithful := Object{"purpose": core.(Object)["purpose"]}
	err := CheckRouting(core, faithful)
	mismatch, isMismatch := err.(RoutingMismatch)
	if !isMismatch || mismatch.Path != "purpose" || mismatch.Because != RoutingIntroducedField {
		t.Fatalf("faithful copy: %v", err)
	}

	// A field nobody signed either, and a nested one whose parent is projected
	// and whose child is not.
	for _, c := range []struct {
		routing Value
		path    string
	}{
		{Object{"shortcut": String("skip-the-checks")}, "shortcut"},
		{Object{"predicate": Object{"elevated": Bool(true)}}, "predicate.elevated"},
	} {
		mismatch, ok := CheckRouting(core, c.routing).(RoutingMismatch)
		if !ok || mismatch.Path != c.path || mismatch.Because != RoutingIntroducedField {
			t.Errorf("%s: %+v", c.path, mismatch)
		}
	}
}

func TestAProjectableNameTheCoreObjectLacksIsIntroduced(t *testing.T) {
	// expires_at is a name §4.5 projects, but a core object without one
	// projects nothing there — so routing carrying it is §2.1's "may never
	// introduce a field", the corpus's routing_introduced_field rather than a
	// value disagreement.
	//
	// Under the older model, which compared against the core object and
	// consulted an allowlist, this was a mismatch. Comparing against the
	// projection makes the two reasons mean what their names say.
	core := Object{"type": String("query")}
	routing := Object{"expires_at": String("2026-07-31T09:05:00Z")}
	mismatch, ok := CheckRouting(core, routing).(RoutingMismatch)
	if !ok || mismatch.Path != "expires_at" || mismatch.Because != RoutingIntroducedField {
		t.Errorf("got %+v", mismatch)
	}
}

func TestAnEmptyPrefixObjectIsAccepted(t *testing.T) {
	// {"target":{}} is not something ProjectRouting emits, and it is refused by
	// nothing: §2.1 asks that routing carry at most the six and introduce no
	// field, and an empty object carries none and introduces none. Rejecting it
	// would be a rule §2.1 does not state.
	//
	// E-42, closed as A, and §2.1 now says so rather than leaving it to be
	// inferred: routing "may carry fewer, or none of them, at any depth — an
	// empty object where a projection could have gone is a projection of
	// nothing, and asserts nothing."
	//
	// It is the one case where "not derivable" and "not permitted" come apart,
	// which is why it was worth a sentence in spec/ rather than a comment here.
	if err := CheckRouting(routingQuery(), Object{"target": Object{}}); err != nil {
		t.Errorf("an empty prefix: %v", err)
	}
}

func TestNothingIsCoerced(t *testing.T) {
	// §4 step 8: same type, same value. A projection whose value is the number
	// 1 does not agree with one that spells it — and a comparison that coerced
	// would let a relay choose the spelling a responder compares.
	core := Object{"expires_at": String("1")}
	numeric := Object{"expires_at": Int(1)}
	err := CheckRouting(core, numeric)
	if mismatch, ok := err.(RoutingMismatch); !ok || mismatch.Because != RoutingSignedMismatch {
		t.Errorf("got %v", err)
	}
}

func TestAnArrayIsComparedWhole(t *testing.T) {
	// No subset rule for arrays: §4.4 makes their order significant, and
	// treating a shorter one as a projection would let a relay drop an element
	// and call it a subset.
	core := Object{"list": Array{Int(1), Int(2)}}
	shortened := Object{"list": Array{Int(1)}}
	if err := CheckRouting(core, shortened); err.(RoutingMismatch).Path != "list" {
		t.Errorf("got %v", err)
	}
}

func TestTheMismatchNamesAPathAndNeverAValue(t *testing.T) {
	// The internal reason is what a responder logs, and the projection is
	// attacker-supplied while the core object is the requester's. An operator
	// needs to know which field; neither value belongs in the record, and
	// neither belongs on the wire.
	core := Object{"nonce": String("the-requesters-nonce")}
	tampered := Object{"nonce": String("the-attackers-nonce")}
	message := CheckRouting(core, tampered).Error()
	if !strings.Contains(message, "nonce") {
		t.Errorf("names no field: %s", message)
	}
	for _, value := range []string{"the-requesters-nonce", "the-attackers-nonce"} {
		if strings.Contains(message, value) {
			t.Errorf("carries %s: %s", value, message)
		}
	}
}

func TestALiteralDottedKeyIsAnIntroducedField(t *testing.T) {
	// §4.5's allowlist is walked segment by segment. Nothing forbids
	// {"predicate.id": …} as a single member name, and comparing a joined
	// "predicate.id" against the allowlist would read that one key as the
	// nested path and admit a field no projection can produce.
	//
	// Both objects carry the literal key, so a dotted comparison would find it
	// in the signed object, call it projectable, and pass.
	core := Object{
		"predicate.id": String("https://q2d.dev/predicates/p"),
		"type":         String("query"),
	}
	routing := Object{"predicate.id": String("https://q2d.dev/predicates/p")}
	mismatch, ok := CheckRouting(core, routing).(RoutingMismatch)
	if !ok || mismatch.Path != "predicate.id" || mismatch.Because != RoutingIntroducedField {
		t.Fatalf("got %+v", mismatch)
	}

	// And the shape §4.5 actually projects is unaffected, which is what makes
	// the segment walk a fix rather than a tightening.
	nested := Object{"predicate": Object{"id": String("https://q2d.dev/predicates/p")}}
	if err := CheckRouting(nested, nested); err != nil {
		t.Errorf("the nested path of the same name: %v", err)
	}
}

func TestAMalformedValueIsComparedRatherThanValidated(t *testing.T) {
	// Step 8 asks whether two values agree, not whether either is well formed.
	// A malformed §2.2 timestamp is refused at the step that owns it — this one
	// only compares.
	//
	// Comparing serialized bytes would import the serializer's validation into
	// the comparison, so an identical malformed expires_at would be a mismatch
	// in Go and equal in Rust, whose == is structural.
	core := Object{
		"expires_at": String("not a date"),
		"type":       String("query"),
	}
	routing := Object{"expires_at": String("not a date")}
	if err := CheckRouting(core, routing); err != nil {
		t.Errorf("identical malformed values disagreed: %v", err)
	}

	// And the serializer does still refuse it, which is what makes this a
	// question about *where* the rule lives rather than whether it exists.
	if _, err := Serialize(core); err == nil {
		t.Error("the fixture no longer exercises a value the profile refuses")
	}
}
