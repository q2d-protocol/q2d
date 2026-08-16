// The replay cache's store — P-004 issue 2.
//
// Key and value are P-004 §4.2's. Retention is spec/freshness.md §1's, and is an
// instant rather than a duration, which this file takes from
// FreshnessPolicy.RetainThrough rather than computing.
//
// # What is here and what is not
//
// The store: insert, look up, evict. The three-way outcome — replay, fresh,
// identifier reuse — is P-004 issue 3, and the atomic commit with the capacity
// debit is issue 5. Both sit above this and neither is a reason to give the store
// an opinion: a store that decided whether a digest matched would be a second
// place the idempotency rule lives.
//
// # The key is (principal, query_id) — and the specification may want more
//
// P-004 §4.2 fixes that key and §9 item 2 makes it escalate-if-changed. But
// core-model.md §5.2.1 says step 9 rejects "a query_id or nonce reused over
// different content", and nothing here tracks nonces: a nonce reused under a new
// query_id is invisible to this store and proceeds as fresh.
//
// The two documents may agree — §5.2.1 may mean the nonce of that identifier,
// which the digest comparison already covers — or the specification may require a
// second index. That is E-50 in docs/open-escalations.md, open, and the store is
// built to P-004 §4.2 meanwhile rather than to a guess. It bites at issue 3,
// which is where the three-way outcome is decided and is not built.
//
// # Only authenticated requests reach it
//
// core-model.md §4 places the replay check at step 9, after signature
// verification at step 4, so nothing unauthenticated can create an entry. That is
// what makes §1's retention bound sufficient to bound the cache: an attacker
// without a valid key cannot fill it, and one with a valid key is bounded by the
// validity window.
//
// Nothing in this file enforces that ordering — a caller could insert at any
// point — and P-004 issue 7 is the assertion that the pipeline does not.
package q2d

import "sort"

// ReplayEntry is one cached exchange. P-004 §4.2's value.
type ReplayEntry struct {
	// RequestDigest is over the exact signed bytes received. Compared on lookup,
	// never keyed on — P-004 §9 item 2.
	RequestDigest string
	// ResponseBytes is the response as it was sent. Bytes, not a decision (§4.5):
	// a replay returns these unchanged rather than re-evaluating, so two retries
	// cannot differ and an escalated outcome cannot become an answer.
	ResponseBytes []byte
	// retainThrough is the instant this entry must be retained through,
	// inclusive.
	retainThrough int64
}

// RetainThrough returns the retention instant, for tests and operator tooling.
func (e ReplayEntry) RetainThrough() int64 { return e.retainThrough }

type replayKey struct {
	principal string
	queryID   string
}

// ReplayCache is the store.
type ReplayCache struct {
	entries map[replayKey]ReplayEntry
}

// NewReplayCache returns an empty store.
func NewReplayCache() *ReplayCache {
	return &ReplayCache{entries: map[replayKey]ReplayEntry{}}
}

// Insert records an exchange.
//
// expiresAt is the request's, in seconds, and the retention instant is derived
// from it by policy — this file never computes a duration. An entry for a key
// already present is replaced, which is the caller's decision to have made: issue
// 3 decides whether a second request under one query_id is a replay or a
// rejection, and by the time it inserts it has already decided.
func (c *ReplayCache) Insert(policy FreshnessPolicy, principal, queryID, requestDigest string, responseBytes []byte, expiresAt int64) {
	// The response is copied. A caller retaining the slice it passed could
	// otherwise mutate a cached response after the fact, and §4.5's whole point
	// is that the bytes returned on a replay are the bytes that were sent.
	stored := make([]byte, len(responseBytes))
	copy(stored, responseBytes)
	c.entries[replayKey{principal, queryID}] = ReplayEntry{
		RequestDigest: requestDigest,
		ResponseBytes: stored,
		retainThrough: policy.RetainThrough(expiresAt),
	}
}

// Get looks up an exchange, as of now.
//
// Retention is applied here and not only by Evict, so a caller sees the same
// answer whether or not eviction has run. A store whose answers depended on when
// a sweep last happened would make idempotency depend on a timer.
//
// Inclusive: an entry is returned at its retention instant, because
// spec/freshness.md §2 still accepts the request then. An entry that stopped
// being visible one second early would let a retry through as fresh — which
// debits twice, and is the defect that boundary exists to close.
//
// The returned entry is a copy, for the reason Insert copies.
func (c *ReplayCache) Get(principal, queryID string, now int64) (ReplayEntry, bool) {
	entry, ok := c.entries[replayKey{principal, queryID}]
	if !ok || now > entry.retainThrough {
		return ReplayEntry{}, false
	}
	stored := make([]byte, len(entry.ResponseBytes))
	copy(stored, entry.ResponseBytes)
	entry.ResponseBytes = stored
	return entry, true
}

// Evict drops every entry whose request can no longer be accepted.
//
// Strictly past the retention instant, matching Get. Returns how many were
// removed, so that eviction is observable in a test rather than inferred — P-004
// issue 2 asks for exactly that, because a sweep that silently did nothing looks
// identical to one that worked.
func (c *ReplayCache) Evict(now int64) int {
	// Keys collected and sorted before deleting. Deleting during a range over a
	// map is defined in Go, and the sort is not for correctness — it is so that
	// nothing in this file has an order that depends on the map's, which is the
	// rule that keeps a future caller from inheriting one.
	var stale []replayKey
	for key, entry := range c.entries {
		if now > entry.retainThrough {
			stale = append(stale, key)
		}
	}
	sort.Slice(stale, func(i, j int) bool {
		if stale[i].principal != stale[j].principal {
			return stale[i].principal < stale[j].principal
		}
		return stale[i].queryID < stale[j].queryID
	})
	for _, key := range stale {
		delete(c.entries, key)
	}
	return len(stale)
}

// Len returns how many entries are held, for tests and operator tooling.
//
// Counts entries that are still stored, including any past their retention
// instant that Evict has not yet swept. Get will not return those, and the
// difference is deliberate: this is a memory question and Get is a protocol one.
func (c *ReplayCache) Len() int { return len(c.entries) }
