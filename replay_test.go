package q2d

import (
	"bytes"
	"testing"
)

// These mirror src/replay.rs's tests case for case.

const replayExpires int64 = 1000300

const replayPrincipal = "did:key:z6MkRequesterPrincipal"

func insertReplay(cache *ReplayCache, policy FreshnessPolicy, queryID string) {
	cache.Insert(policy, replayPrincipal, queryID, "sha256:aa", []byte("response"), replayExpires)
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
		cache.Insert(policy, "p", "q", "sha256:aa", nil, expires)
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
	if n := cache.Evict(through + 1); n != 2 {
		t.Errorf("evicted %d, want 2", n)
	}
	if cache.Len() != 0 {
		t.Errorf("len %d after eviction", cache.Len())
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
	strict, err := NewFreshnessPolicy(5, 0, 0)
	if err != nil {
		t.Fatal(err)
	}
	cache := NewReplayCache()
	cache.Insert(strict, "p", "q", "sha256:aa", nil, replayExpires)
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
	cache.Insert(policy, "p", "q", "sha256:aa", response, replayExpires)
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
