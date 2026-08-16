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
// # Two indexes, because §5.2.1 names two identifiers
//
// core-model.md §5.2.1 rejects "a query_id or nonce reused over different
// content". The query_id half is the primary key and the digest comparison; the
// nonce half needs its own index, because a nonce reused under a new query_id
// shares no key with its first use.
//
// E-50 settled that, against a recommendation to read the sentence loosely and
// amend it. Two arguments carried it: the specification governs, so "the
// implementation does not do this" is not evidence the specification is wrong —
// and at 128 bits from a CSPRNG a collision is negligible, so the only traffic
// this index refuses is a requester bug.
//
// The nonce index is scoped to the requester, exactly as the primary key is. A
// global index would let any requester exhaust another's nonce values and deny
// them service — a denial-of-service handed to every peer in exchange for
// nothing.
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
	// nonce is the nonce this exchange used, so that replacing the entry can
	// retire the nonce record it wrote. Unexported: it exists to keep the two
	// indexes consistent, not to be read.
	nonce string
}

// RetainThrough returns the retention instant, for tests and operator tooling.
func (e ReplayEntry) RetainThrough() int64 { return e.retainThrough }

// NonceUse is what a nonce this requester has already used was attached to.
//
// Only the digest and the retention instant: this index answers "has this
// requester used this nonce, and over what content", and a response body here
// would be a second copy of one the primary index already holds.
type NonceUse struct {
	// RequestDigest is the digest of the request that used it.
	RequestDigest string
	retainThrough int64
}

// RetainThrough returns the retention instant.
func (n NonceUse) RetainThrough() int64 { return n.retainThrough }

type replayKey struct {
	principal string
	queryID   string
}

type nonceKey struct {
	principal string
	nonce     string
}

// ReplayCache is the store.
type ReplayCache struct {
	entries map[replayKey]ReplayEntry
	nonces  map[nonceKey]NonceUse
}

// NewReplayCache returns an empty store.
func NewReplayCache() *ReplayCache {
	return &ReplayCache{
		entries: map[replayKey]ReplayEntry{},
		nonces:  map[nonceKey]NonceUse{},
	}
}

// Insert records an exchange.
//
// expiresAt is the request's, in seconds, and the retention instant is derived
// from it by policy — this file never computes a duration. An entry for a key
// already present is replaced, which is the caller's decision to have made: issue
// 3 decides whether a second request under one query_id is a replay or a
// rejection, and by the time it inserts it has already decided.
func (c *ReplayCache) Insert(policy FreshnessPolicy, principal, queryID, requestDigest string, responseBytes []byte, nonce string, expiresAt int64) {
	// The response is copied. A caller retaining the slice it passed could
	// otherwise mutate a cached response after the fact, and §4.5's whole point
	// is that the bytes returned on a replay are the bytes that were sent.
	stored := make([]byte, len(responseBytes))
	copy(stored, responseBytes)
	retainThrough := policy.RetainThrough(expiresAt)
	// Both indexes are written in one call and expire at one instant, so there is
	// no state in which a request is remembered by one and not the other. Two
	// insert functions would make that state reachable.
	//
	// Including on replace, which review found this had not handled: an entry
	// overwritten under one query_id with a different nonce used to leave its
	// first nonce remembered with nothing pointing at it. That failed restrictive
	// — the stale record would reject a later reuse — and the comment above was
	// false, which is worse than the leak.
	//
	// Nothing in the pipeline replaces an entry: issue 3 decides fresh, replay or
	// reuse before inserting, and a fresh request carries a new identifier. The
	// invariant is held here anyway, because a store whose documented invariant
	// depends on its caller's discipline does not have one.
	if previous, ok := c.entries[replayKey{principal, queryID}]; ok && previous.nonce != nonce {
		delete(c.nonces, nonceKey{principal, previous.nonce})
	}
	c.entries[replayKey{principal, queryID}] = ReplayEntry{
		RequestDigest: requestDigest,
		ResponseBytes: stored,
		retainThrough: retainThrough,
		nonce:         nonce,
	}
	c.nonces[nonceKey{principal, nonce}] = NonceUse{
		RequestDigest: requestDigest,
		retainThrough: retainThrough,
	}
}

// NonceUsed reports what this requester last used nonce for, as of now.
//
// The second return is false where it has not used it inside the retention
// window. A caller comparing the returned digest against the request in hand gets
// §5.2.1's distinction: equal is the same request arriving again, which the
// primary index will report as a retry, and different is the nonce reused over
// different content, which is a rejection.
//
// This deliberately does not make that decision. Issue 3 owns the outcome, and a
// store with an opinion about it would be a second place the rule lives.
func (c *ReplayCache) NonceUsed(principal, nonce string, now int64) (NonceUse, bool) {
	use, ok := c.nonces[nonceKey{principal, nonce}]
	if !ok || now > use.retainThrough {
		return NonceUse{}, false
	}
	return use, true
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

	// Both indexes, because both are bounded by the same instant and an eviction
	// that swept one would leave the other unbounded — which is the memory
	// argument spec/freshness.md §1 makes, applied to the index added after it.
	var staleNonces []nonceKey
	for key, use := range c.nonces {
		if now > use.retainThrough {
			staleNonces = append(staleNonces, key)
		}
	}
	sort.Slice(staleNonces, func(i, j int) bool {
		if staleNonces[i].principal != staleNonces[j].principal {
			return staleNonces[i].principal < staleNonces[j].principal
		}
		return staleNonces[i].nonce < staleNonces[j].nonce
	})
	for _, key := range staleNonces {
		delete(c.nonces, key)
	}
	return len(stale) + len(staleNonces)
}

// Len returns how many entries are held, for tests and operator tooling.
//
// Counts entries that are still stored, including any past their retention
// instant that Evict has not yet swept. Get will not return those, and the
// difference is deliberate: this is a memory question and Get is a protocol one.
func (c *ReplayCache) Len() int { return len(c.entries) }

// NonceLen returns how many nonce records are held.
//
// Separate from Len rather than summed into it: they are written together and
// evicted together, so a test that could only see a total could not tell a store
// that dropped one index from a store that dropped both.
func (c *ReplayCache) NonceLen() int { return len(c.nonces) }
