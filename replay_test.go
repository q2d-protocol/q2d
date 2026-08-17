package q2d

import (
	"bytes"
	"errors"
	"testing"
)

// These mirror src/replay.rs's tests case for case, with one exception:
// TestAReservationWithNoBudgetIsRefused has no Rust counterpart, because Rust's
// generic parameter cannot be absent and there is no case to write.

const replayExpires int64 = 1000300

const replayPrincipal = "did:key:z6MkRequesterPrincipal"

func insertReplay(cache *ReplayCache, policy FreshnessPolicy, queryID string) {
	cache.insert(policy, replayPrincipal, queryID, "sha256:aa", []byte("response"), "nonce-for-"+queryID, replayExpires)
}

func TestAnEntryIsReturnedVerbatim(t *testing.T) {
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	insertReplay(cache, policy, "urn:uuid:one")
	entry, ok := cache.Get(replayPrincipal, "urn:uuid:one", replayExpires)
	if !ok {
		t.Fatal("absent")
	}
	if !bytes.Equal(entry.ResponseBytes, []byte("response")) {
		t.Errorf("response %q", entry.ResponseBytes)
	}
	if entry.RequestDigest != "sha256:aa" {
		t.Errorf("digest %q", entry.RequestDigest)
	}
}

func TestTheKeyIsThePrincipalAndTheQueryID(t *testing.T) {
	// Both halves. One requester's identifier must not reach another's entry, and
	// a second identifier from the same requester is a different exchange.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	insertReplay(cache, policy, "urn:uuid:one")
	if _, ok := cache.Get("did:key:z6MkSomeoneElse", "urn:uuid:one", replayExpires); ok {
		t.Error("another principal reached this entry")
	}
	if _, ok := cache.Get(replayPrincipal, "urn:uuid:two", replayExpires); ok {
		t.Error("another query_id reached this entry")
	}
}

func TestRetentionIsInclusiveAtTheInstant(t *testing.T) {
	// The boundary E-49's review found. An entry visible until retainThrough and
	// not at it is evicted one second early, and spec/freshness.md §2 still
	// accepts the request then — so the retry arrives as fresh and debits again.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	insertReplay(cache, policy, "urn:uuid:one")
	through := policy.RetainThrough(replayExpires)
	if _, ok := cache.Get(replayPrincipal, "urn:uuid:one", through); !ok {
		t.Error("evicted at the instant it is still acceptable")
	}
	if _, ok := cache.Get(replayPrincipal, "urn:uuid:one", through+1); ok {
		t.Error("visible after the instant")
	}
}

func TestTheCacheNeverHidesAnEntryTheFreshnessCheckWouldAccept(t *testing.T) {
	// The relationship rather than the numbers, across every window a request may
	// carry. This is the invariant the two files share: if §2 accepts, the entry
	// is visible.
	policy := DefaultFreshnessPolicy()
	for window := int64(1); window <= 300; window++ {
		issued, expires := int64(1000000), int64(1000000)+window
		cache := NewReplayCache()
		cache.insert(policy, "p", "q", "sha256:aa", nil, "n", expires)
		for now := issued - 120; now <= expires+120; now++ {
			acceptable := policy.Check(issued, expires, now) == nil
			_, visible := cache.Get("p", "q", now)
			if acceptable && !visible {
				t.Fatalf("window %d, now %d: acceptable and not visible", window, now)
			}
		}
	}
}

func TestEvictionIsObservableAndStrictlyPastTheInstant(t *testing.T) {
	// P-004 issue 2 asks for eviction observable in a test rather than inferred,
	// so Evict reports a count: a sweep that silently did nothing looks identical
	// to one that worked.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	insertReplay(cache, policy, "urn:uuid:one")
	insertReplay(cache, policy, "urn:uuid:two")
	through := policy.RetainThrough(replayExpires)
	if n := cache.Evict(through); n != 0 {
		t.Errorf("evicted %d entries that are still acceptable", n)
	}
	if cache.Len() != 2 {
		t.Errorf("len %d", cache.Len())
	}
	// Four: two entries and their two nonce records, which expire together
	// because they were written together.
	if n := cache.Evict(through + 1); n != 4 {
		t.Errorf("evicted %d, want 4", n)
	}
	if cache.Len() != 0 || cache.NonceLen() != 0 {
		t.Errorf("len %d, nonces %d after eviction", cache.Len(), cache.NonceLen())
	}
}

func TestLookupDoesNotDependOnWhetherASweepHasRun(t *testing.T) {
	// Retention is applied on read as well as by the sweep. A store whose answers
	// depended on a timer would make idempotency depend on one.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	insertReplay(cache, policy, "urn:uuid:one")
	after := policy.RetainThrough(replayExpires) + 1
	if _, ok := cache.Get(replayPrincipal, "urn:uuid:one", after); ok {
		t.Error("visible past retention before a sweep")
	}
	if cache.Len() != 1 {
		t.Errorf("len %d — still stored, and not visible", cache.Len())
	}
	cache.Evict(after)
	if _, ok := cache.Get(replayPrincipal, "urn:uuid:one", after); ok {
		t.Error("visible after a sweep")
	}
}

func TestAShorterConfiguredWindowShortensRetention(t *testing.T) {
	// Configuration may only make a responder stricter, and retention is derived —
	// so a tighter skew produces a shorter retention without this file knowing
	// anything about configuration.
	strict, err := NewFreshnessPolicy(FreshnessConfig{Skew: seconds(5)})
	if err != nil {
		t.Fatal(err)
	}
	cache := NewReplayCache()
	cache.insert(strict, "p", "q", "sha256:aa", nil, "n", replayExpires)
	if _, ok := cache.Get("p", "q", replayExpires+5); !ok {
		t.Error("evicted inside the configured skew")
	}
	if _, ok := cache.Get("p", "q", replayExpires+6); ok {
		t.Error("visible past the configured skew")
	}
}

func TestAStoredResponseCannotBeMutatedThroughTheCallersSlice(t *testing.T) {
	// Go-specific, and CONVENTIONS-go.md's deep-copy rule: Rust gets this from the
	// borrow checker — Insert takes ownership and Get lends immutably — where a Go
	// caller retaining its slice could otherwise rewrite a cached response after
	// the fact. §4.5's whole point is that a replay returns the bytes that were
	// sent.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	response := []byte("answer")
	cache.insert(policy, "p", "q", "sha256:aa", response, "n", replayExpires)
	response[0] = 'X'
	entry, _ := cache.Get("p", "q", replayExpires)
	if !bytes.Equal(entry.ResponseBytes, []byte("answer")) {
		t.Errorf("the cached response changed with the caller's slice: %q", entry.ResponseBytes)
	}
	entry.ResponseBytes[0] = 'Y'
	again, _ := cache.Get("p", "q", replayExpires)
	if !bytes.Equal(again.ResponseBytes, []byte("answer")) {
		t.Errorf("the cached response changed through a returned entry: %q", again.ResponseBytes)
	}
}

func TestANonceIsFoundUnderADifferentQueryID(t *testing.T) {
	// The case the primary index cannot see, and the whole of E-50. A nonce reused
	// under a new identifier shares no key with its first use, so without this
	// index the second request is fresh.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	cache.insert(policy, "p", "urn:uuid:one", "sha256:aa", nil, "N", replayExpires)
	if _, ok := cache.Get("p", "urn:uuid:two", replayExpires); ok {
		t.Error("the primary index saw it, which it cannot")
	}
	use, ok := cache.NonceUsed("p", "N", replayExpires)
	if !ok {
		t.Fatal("the nonce index did not")
	}
	if use.RequestDigest != "sha256:aa" {
		t.Errorf("digest %q", use.RequestDigest)
	}
}

func TestTheNonceIndexIsScopedToTheRequester(t *testing.T) {
	// A global index would let any requester exhaust another's nonce values and
	// deny them service.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	cache.insert(policy, "p", "q", "sha256:aa", nil, "N", replayExpires)
	if _, ok := cache.NonceUsed("someone-else", "N", replayExpires); ok {
		t.Error("one requester's nonce reached another's index")
	}
}

func TestTheStoreReportsTheDigestAndTakesNoView(t *testing.T) {
	// §5.2.1's distinction is the caller's to draw: an equal digest is the same
	// request arriving again, a different one is the reuse. A store that decided
	// would be a second place the rule lives — which is why this returns what it
	// recorded rather than a verdict.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	cache.insert(policy, "p", "q", "sha256:aa", nil, "N", replayExpires)
	use, _ := cache.NonceUsed("p", "N", replayExpires)
	if use.RequestDigest != "sha256:aa" {
		t.Errorf("digest %q", use.RequestDigest)
	}
}

func TestBothIndexesExpireAtTheSameInstant(t *testing.T) {
	// Written together and evicted together, so no state exists in which a request
	// is remembered by one and not the other.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	cache.insert(policy, "p", "q", "sha256:aa", nil, "N", replayExpires)
	through := policy.RetainThrough(replayExpires)
	if _, ok := cache.Get("p", "q", through); !ok {
		t.Error("entry gone at the instant")
	}
	if _, ok := cache.NonceUsed("p", "N", through); !ok {
		t.Error("nonce record gone at the instant")
	}
	if _, ok := cache.Get("p", "q", through+1); ok {
		t.Error("entry visible after the instant")
	}
	if _, ok := cache.NonceUsed("p", "N", through+1); ok {
		t.Error("nonce record visible after the instant")
	}
}

func TestReplacingAnEntryRetiresTheNonceItReplaced(t *testing.T) {
	// Review found this: the two indexes could diverge on replace, leaving a nonce
	// remembered with nothing pointing at it. Nothing in the pipeline replaces an
	// entry, and a documented invariant that depends on the caller's discipline is
	// not one.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	cache.insert(policy, "p", "q", "sha256:aa", nil, "first", replayExpires)
	cache.insert(policy, "p", "q", "sha256:bb", nil, "second", replayExpires)
	if _, ok := cache.NonceUsed("p", "first", replayExpires); ok {
		t.Error("the replaced nonce is still remembered")
	}
	if _, ok := cache.NonceUsed("p", "second", replayExpires); !ok {
		t.Error("the replacing nonce is not remembered")
	}
	if cache.NonceLen() != 1 {
		t.Errorf("%d nonce records for one exchange", cache.NonceLen())
	}
	// And replacing with the same nonce keeps it, rather than deleting the record
	// it is about to write.
	cache.insert(policy, "p", "q", "sha256:cc", nil, "second", replayExpires)
	use, ok := cache.NonceUsed("p", "second", replayExpires)
	if !ok || use.RequestDigest != "sha256:cc" {
		t.Errorf("%+v %v", use, ok)
	}
}

func TestTheFourOutcomes(t *testing.T) {
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	if got, _ := cache.Check("p", "q1", "n1", "sha256:aa", replayExpires); got != ReplayFresh {
		t.Errorf("nothing recorded: %v, want fresh", got)
	}

	cache.insert(policy, "p", "q1", "sha256:aa", []byte("answer"), "n1", replayExpires)

	got, response := cache.Check("p", "q1", "n1", "sha256:aa", replayExpires)
	if got != ReplayReplayed || !bytes.Equal(response, []byte("answer")) {
		t.Errorf("retry: %v %q", got, response)
	}
	if got, _ := cache.Check("p", "q1", "n1", "sha256:bb", replayExpires); got != ReplayQueryIDReuse {
		t.Errorf("same query_id, different content: %v", got)
	}
	// E-50's case, and the one the primary index alone cannot see.
	if got, _ := cache.Check("p", "q2", "n1", "sha256:bb", replayExpires); got != ReplayNonceReuse {
		t.Errorf("nonce reused under a new identifier: %v", got)
	}
	if got, _ := cache.Check("p", "q2", "n2", "sha256:bb", replayExpires); got != ReplayFresh {
		t.Errorf("a wholly new request: %v", got)
	}
}

func TestARetryIsAReplayAndNotANonceReuse(t *testing.T) {
	// Why the query_id index is consulted first. A genuine retry matches both
	// indexes, so a nonce-first order would have to special-case it — and a rule
	// with an exception carved out for the common case is a rule waiting to be got
	// wrong.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	cache.insert(policy, "p", "q", "sha256:aa", []byte("answer"), "n", replayExpires)
	if _, ok := cache.NonceUsed("p", "n", replayExpires); !ok {
		t.Fatal("both indexes should match")
	}
	if got, _ := cache.Check("p", "q", "n", "sha256:aa", replayExpires); got != ReplayReplayed {
		t.Errorf("%v, want replayed", got)
	}
}

func TestAReplayReturnsTheBytesThatWereStored(t *testing.T) {
	// Issue 6. Not re-evaluated and not re-signed: re-signing regenerates
	// decided_at, two retries would differ, and that difference tells a requester
	// the responder re-evaluated — which under opaque escalation is what §5.3
	// forbids revealing.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	cache.insert(policy, "p", "q", "sha256:aa", []byte("exactly these"), "n", replayExpires)
	_, first := cache.Check("p", "q", "n", "sha256:aa", replayExpires)
	_, second := cache.Check("p", "q", "n", "sha256:aa", replayExpires)
	if !bytes.Equal(first, second) {
		t.Errorf("two retries differ: %q %q", first, second)
	}
	if !bytes.Equal(first, []byte("exactly these")) {
		t.Errorf("%q", first)
	}
}

func TestAnExpiredEntryMakesTheRequestFreshAgain(t *testing.T) {
	// Both indexes stop answering at the same instant, so a request past retention
	// is fresh rather than half-remembered. It cannot actually reach step 9 — §2
	// rejects it at step 6 — and the store does not rely on that, because a store
	// that depended on a caller checking first would be a store with an
	// undocumented precondition.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	cache.insert(policy, "p", "q", "sha256:aa", nil, "n", replayExpires)
	after := policy.RetainThrough(replayExpires) + 1
	if got, _ := cache.Check("p", "q", "n", "sha256:aa", after); got != ReplayFresh {
		t.Errorf("%v, want fresh", got)
	}
}

func TestTheTwoRejectionsAreToldApartInternallyAndShareAStep(t *testing.T) {
	// The wire value is deliberately absent from this type: §5.2.1 gives
	// everything from step 9 onward the value the responder's pinned registry
	// declares, which is data. A constant here would compile one deployment's
	// configuration into every deployment.
	seen := map[string]struct{}{}
	for _, o := range []ReplayOutcome{ReplayQueryIDReuse, ReplayNonceReuse} {
		seen[o.InternalReason()] = struct{}{}
		if o.Step() != "9" {
			t.Errorf("%v at step %q", o, o.Step())
		}
	}
	if len(seen) != 2 {
		t.Error("an operator cannot tell the two rejections apart")
	}
	// And the two non-rejections name no reason and no step.
	for _, o := range []ReplayOutcome{ReplayFresh, ReplayReplayed} {
		if o.InternalReason() != "" || o.Step() != "" {
			t.Errorf("%v reports %q at %q", o, o.InternalReason(), o.Step())
		}
	}
}

// ---- issue 5: the commit, and the fault injection around it ----

// testBudget keeps a running total and can be made to refuse.
//
// The total is what the assertions read, not the call count: P-004 §7 asks for a
// retry to produce no second debit against the budget total, and a call count
// would pass for a store that was called once and applied the value twice. The
// double's reservation carries the millibits so that a total exists to assert
// against — the code under test never sees one, which is the point of the
// reservation and is itself asserted below.
//
// refuse is the fault injection, and it refuses the way Budget says a refusal
// works: nothing is committed. A double that applied the debit and then reported
// failure would contradict the one contract Record relies on, and would be
// asserting the behaviour of a store that may not exist. The crash after a
// successful settle is a different state and is reached differently — see the
// over-charge test.
type testBudget struct {
	total   int64
	refuse  bool
	settled int
}

// testReservation is P-008's reservation, reduced to what a test needs to add up.
type testReservation struct{ millibits int64 }

// errRefused is everything P-008 will say, reduced to the one thing this file
// needs.
var errRefused = errors.New("refused")

func (b *testBudget) Settle(reservation Reservation) error {
	b.settled++
	if b.refuse {
		return errRefused
	}
	b.total += reservation.(testReservation).millibits
	return nil
}

func recordReplay(cache *ReplayCache, budget Budget, policy FreshnessPolicy, queryID string, debit int64) error {
	return cache.Record(budget, policy, replayPrincipal, queryID, "nonce-for-"+queryID,
		"sha256:aa", []byte("response"), replayExpires, testReservation{debit})
}

func TestACommitWritesBothIndexesAndDebitsOnce(t *testing.T) {
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	budget := &testBudget{}
	if err := recordReplay(cache, budget, policy, "urn:uuid:one", 2000); err != nil {
		t.Fatalf("committed: %v", err)
	}
	if budget.total != 2000 {
		t.Errorf("total %d", budget.total)
	}
	if budget.settled != 1 {
		t.Errorf("%d settles; one exchange settles once", budget.settled)
	}
	if cache.Len() != 1 || cache.NonceLen() != 1 {
		t.Errorf("%d entries, %d nonces", cache.Len(), cache.NonceLen())
	}
}

func TestARefusedDebitLeavesNoEntry(t *testing.T) {
	// The fault injection, and the property is the absence: an entry written
	// beside a debit that did not happen is the under-charge — a retry would find
	// it, return the stored bytes, and the disclosure would never be paid for.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	budget := &testBudget{refuse: true}
	err := recordReplay(cache, budget, policy, "urn:uuid:one", 2000)
	if !errors.Is(err, errRefused) {
		t.Fatalf("err %v; P-008's reason should pass back untouched", err)
	}
	if budget.total != 0 {
		t.Errorf("total %d", budget.total)
	}
	if cache.Len() != 0 || cache.NonceLen() != 0 {
		t.Errorf("%d entries, %d nonces; neither index should have been written", cache.Len(), cache.NonceLen())
	}
}

func TestARefusedDebitLeavesAnEarlierExchangeAlone(t *testing.T) {
	// The refusal must not be a rollback of something else. An earlier exchange
	// under a different identifier is committed and paid for, and a later refusal
	// has no business touching it.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	budget := &testBudget{}
	if err := recordReplay(cache, budget, policy, "urn:uuid:one", 2000); err != nil {
		t.Fatalf("committed: %v", err)
	}
	budget.refuse = true
	if err := recordReplay(cache, budget, policy, "urn:uuid:two", 2000); err == nil {
		t.Fatal("the second commit should have been refused")
	}
	if budget.total != 2000 {
		t.Errorf("total %d", budget.total)
	}
	if cache.Len() != 1 {
		t.Errorf("%d entries", cache.Len())
	}
	if _, ok := cache.Get(replayPrincipal, "urn:uuid:one", replayExpires); !ok {
		t.Error("the earlier exchange was lost")
	}
}

func TestACrashAfterTheSettleOverChargesRatherThanUnderCharging(t *testing.T) {
	// §4.6's first row, which is the state settle-first leaves open and the reason
	// it is nevertheless the safe side. The capacity is spent, no entry exists, and
	// nothing gives it back: the reservation settled, so the expiry that covers an
	// abandoned one does not apply here.
	//
	// The crash is modelled by doing what Record does and stopping where it would
	// have stopped — settle returns, the entry is never written. Asking the double
	// to apply a debit and then report failure would produce the same state by
	// contradicting Budget's contract, which is the one thing Record relies on.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	budget := &testBudget{}
	if err := budget.Settle(testReservation{2000}); err != nil {
		t.Fatalf("settled: %v", err)
	}
	// ... and the process dies here, between the two writes.
	if budget.total != 2000 {
		t.Errorf("total %d; the capacity is spent", budget.total)
	}
	if cache.Len() != 0 {
		t.Errorf("%d entries", cache.Len())
	}

	outcome, _ := cache.Check(replayPrincipal, "urn:uuid:one", "nonce-for-urn:uuid:one", "sha256:aa", replayExpires)
	if outcome != ReplayFresh {
		t.Fatalf("outcome %v; nothing should suppress the retry", outcome)
	}
	if err := recordReplay(cache, budget, policy, "urn:uuid:one", 2000); err != nil {
		t.Fatalf("committed: %v", err)
	}
	if budget.total != 4000 {
		t.Errorf("total %d; charged twice is the safe side", budget.total)
	}
}

func TestARetryOfACommittedExchangeDoesNotDebitAgain(t *testing.T) {
	// P-004 §7, and the reason Check and Record are separate calls: the retry
	// never reaches the commit, because step 9 has already answered.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	budget := &testBudget{}
	if err := recordReplay(cache, budget, policy, "urn:uuid:one", 2000); err != nil {
		t.Fatalf("committed: %v", err)
	}
	outcome, stored := cache.Check(replayPrincipal, "urn:uuid:one", "nonce-for-urn:uuid:one", "sha256:aa", replayExpires)
	if outcome != ReplayReplayed || !bytes.Equal(stored, []byte("response")) {
		t.Fatalf("outcome %v, bytes %q", outcome, stored)
	}
	if budget.total != 2000 {
		t.Errorf("total %d; one exchange, one debit", budget.total)
	}
}

func TestTheAmountNeverReachesThisPackage(t *testing.T) {
	// P-008 §5's structural property, from this side. check returns a reservation
	// rather than a boolean so that a caller cannot commit capacity it never
	// reserved — and that only holds if the commit takes the reservation. A
	// millibit parameter here would let a caller pass a number it invented, which
	// is the same hole with an extra step.
	//
	// The signature carries it: Record takes an opaque Reservation, so this
	// package has nothing to inspect, no arithmetic to do, and no value to get
	// wrong. A negative or absurd amount is P-008's to refuse, where the
	// arithmetic lives. All this can assert is that the amount came from the
	// reservation and not from a parameter.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	budget := &testBudget{}
	if err := cache.Record(budget, policy, replayPrincipal, "urn:uuid:one", "n", "sha256:aa",
		[]byte("response"), replayExpires, testReservation{2000}); err != nil {
		t.Fatalf("committed: %v", err)
	}
	if budget.total != 2000 {
		t.Errorf("total %d; the amount was the reservation's", budget.total)
	}
}

func TestADenialCommitsWithNoReservation(t *testing.T) {
	// §4.7 caches every outcome from step 9 onward, and E-01 settled that deny and
	// escalate debit nothing — so most cached outcomes have no reservation at all.
	// A required one would force a caller either to skip caching denials, which
	// lets a denial become an answer on retry, or to mint an empty reservation,
	// which is a debit-shaped object where E-01 says none belongs.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	budget := &testBudget{}
	if err := cache.Record(budget, policy, replayPrincipal, "urn:uuid:one", "n", "sha256:aa",
		[]byte("denied"), replayExpires, nil); err != nil {
		t.Fatalf("committed: %v", err)
	}
	if budget.settled != 0 {
		t.Errorf("%d settles; nothing should have been settled", budget.settled)
	}
	if budget.total != 0 {
		t.Errorf("total %d", budget.total)
	}
	if cache.Len() != 1 {
		t.Errorf("%d entries; the outcome is cached anyway", cache.Len())
	}
	// And it is returned verbatim on a retry, which is the whole point: a denial
	// that re-evaluated could come back as something else.
	outcome, stored := cache.Check(replayPrincipal, "urn:uuid:one", "n", "sha256:aa", replayExpires)
	if outcome != ReplayReplayed || !bytes.Equal(stored, []byte("denied")) {
		t.Errorf("outcome %v, bytes %q", outcome, stored)
	}
}

func TestAReservationWithNoBudgetIsRefused(t *testing.T) {
	// Go's interfaces admit a nil where Rust's generic parameter cannot be absent
	// — CONVENTIONS-go.md §4. A reservation handed to no budget would be dropped
	// silently and the entry committed against capacity nobody spent, so it is a
	// named refusal. A nil reservation is not: that is a denial, and the test
	// above is it.
	cache, policy := NewReplayCache(), DefaultFreshnessPolicy()
	if err := recordReplay(cache, nil, policy, "urn:uuid:one", 2000); !errors.Is(err, ErrNoBudget) {
		t.Errorf("err %v", err)
	}
	if cache.Len() != 0 {
		t.Errorf("%d entries", cache.Len())
	}
}
