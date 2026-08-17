// The replay cache's store — P-004 issue 2.
//
// Key and value are P-004 §4.2's. Retention is spec/freshness.md §1's, and is an
// instant rather than a duration, which this file takes from
// FreshnessPolicy.RetainThrough rather than computing.
//
// # What is here and what is not
//
// The two indexes, Check — step 9's four-way outcome over them: fresh, replay,
// query_id reuse, nonce reuse — and Record, the commit of an outcome together
// with its capacity debit. The decision lives with the indexes rather than above
// them because it is a reading of both, and a caller assembling it from Get and
// NonceUsed would be the second place the order of those two lookups is decided
// — which is the part §5.2.1 constrains.
//
// Not here: the budget arithmetic behind Budget, which is P-008's, and when step
// 9 runs, which is the pipeline's and is issue 7.
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

import (
	"errors"
	"sort"
)

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

// insert writes both indexes.
//
// expiresAt is the request's, in seconds, and the retention instant is derived
// from it by policy — this file never computes a duration. An entry for a key
// already present is replaced, which is the caller's decision to have made: issue
// 3 decides whether a second request under one query_id is a replay or a
// rejection, and by the time it inserts it has already decided.
//
// Unexported since issue 5. Record is the only way to commit an exchange, because
// §4.6's guarantee is that an entry and its debit arrive together — and an
// exported writer that took no debit would be a second commit path with the debit
// left out, which is the under-charge the issue exists to prevent. The store's own
// tests still reach it: they are testing the indexes, not the commit.
func (c *ReplayCache) insert(policy FreshnessPolicy, principal, queryID, requestDigest string, responseBytes []byte, nonce string, expiresAt int64) {
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
// It reports rather than concludes, and Check is what draws the conclusion — kept
// separate so that a caller needing to know whether a nonce has been seen does not
// have to run the whole of step 9 to find out.
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

// ReplayOutcome is what step 9 concluded — P-004 §4.2, extended to four cases by
// E-50.
type ReplayOutcome int

const (
	// ReplayFresh: no record of this exchange. Proceed.
	ReplayFresh ReplayOutcome = iota
	// ReplayReplayed: the same request arriving again. The stored bytes,
	// verbatim — P-004 §4.5, and issue 6: not re-evaluated and not re-signed,
	// because re-signing regenerates decided_at and two retries would differ.
	// That difference tells a requester the responder re-evaluated, which under
	// opaque escalation is the state transition core-model.md §5.3 forbids
	// revealing.
	ReplayReplayed
	// ReplayQueryIDReuse: same query_id, different content — P-004 §4.2's third
	// row.
	//
	// A decision rather than a fallout: it could be a requester retrying after
	// correcting a contract, or an attacker probing for cache confusion.
	// Rejecting makes one query_id mean one exchange, and a requester needing to
	// correct a request issues a new identifier.
	ReplayQueryIDReuse
	// ReplayNonceReuse: same nonce, different content, under a different
	// query_id — E-50.
	ReplayNonceReuse
)

// InternalReason is the corpus's name for a rejecting outcome, and empty for the
// two that are not rejections.
//
// There is deliberately no ExternalReason here, and the reason is not tidiness.
// Every reason in the Rejected type maps to a wire value fixed by core-model.md
// §5.2.1's table. These two do not: §5.2.1 gives everything from step 9 onward
// the value the responder's pinned registry declares — denial_normalization,
// which is unavailable in the reference manifest and is data. A constant here
// would be one deployment's configuration compiled into every deployment. P-009
// builds the response and reads the registry.
func (o ReplayOutcome) InternalReason() string {
	switch o {
	case ReplayQueryIDReuse:
		return "query_id_reuse"
	case ReplayNonceReuse:
		return "nonce_reuse"
	default:
		return ""
	}
}

// Step is core-model.md §4's step. Always 9 for a rejecting outcome, empty
// otherwise.
func (o ReplayOutcome) Step() string {
	if o == ReplayQueryIDReuse || o == ReplayNonceReuse {
		return "9"
	}
	return ""
}

// Check is core-model.md §4 step 9, over both indexes.
//
// The second return carries the stored response, and is non-nil only for
// ReplayReplayed.
//
// # Order, and why it is this one
//
// The query_id index first. A genuine retry matches there, and its nonce record
// necessarily matches too — so consulting the nonce index first would have to
// special-case the retry to avoid rejecting it, and a rule with an exception
// carved out for the common case is a rule waiting to be got wrong.
//
// # The case that cannot happen, and is handled anyway
//
// A nonce record whose digest equals the request's, reached after the query_id
// index found nothing, is a contradiction: equal digests mean equal signed bytes,
// and query_id is inside those bytes, so the primary index would have found it.
// It is treated as a rejection rather than waved through, because the alternative
// is deciding that an impossible state is safe.
func (c *ReplayCache) Check(principal, queryID, nonce, requestDigest string, now int64) (ReplayOutcome, []byte) {
	if entry, ok := c.Get(principal, queryID, now); ok {
		if entry.RequestDigest == requestDigest {
			return ReplayReplayed, entry.ResponseBytes
		}
		return ReplayQueryIDReuse, nil
	}
	if _, ok := c.NonceUsed(principal, nonce, now); ok {
		return ReplayNonceReuse, nil
	}
	return ReplayFresh, nil
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

// Reservation is P-008 §5's reservation handle, opaque to this file.
//
// P-008's check returns one rather than a boolean so that a caller "cannot check
// and then debit later without holding the thing that reserved the capacity". An
// interface value carries it here because what a reservation is belongs to P-008,
// exactly as Rust makes it an associated type; this file only passes it on.
type Reservation any

// Budget is where the capacity debit is settled — P-008 §5's settle, which that
// PRD says is called from this file's Record.
//
// This file calls it and does not implement it. P-004 §3 puts budget arithmetic
// in P-008; what is here is where the debit is committed, and that needs a seam
// rather than a sum.
//
// # It takes a reservation, not a quantity
//
// A millibit count here would hand back the property the reservation exists for:
// anyone could commit an entry against a number they made up, having reserved
// nothing. So this file never sees an amount, and consequently has no opinion
// about one — a negative or absurd value is refused where the arithmetic is,
// which is P-008.
//
// The returned error is P-008's and is passed back by Record unchanged, because
// what a refusal means — insufficient remaining capacity, an unknown principal, a
// store that is down — is P-008's to say. A nil error means committed; a non-nil
// one means nothing was committed, which is what Record relies on to leave the
// cache untouched. The reservation is consumed either way: one that fails to
// settle stays with P-008, where an unsettled reservation expires (P-010 §4.7),
// so the capacity returns rather than being stranded.
type Budget interface {
	Settle(reservation Reservation) error
}

// ErrNoBudget is Record called with no budget to settle against, and
// ErrNoReservation is Record called with no reservation to settle.
//
// Go's interfaces admit a nil where Rust's generic parameters cannot be absent,
// so both refusals exist on one side only — CONVENTIONS-go.md §4's rule that a
// nil interface value is a distinct case and gets a named refusal. What both
// implementations agree on is that no entry is committed without a settled
// reservation.
var (
	ErrNoBudget      = errors.New("q2d: no budget to settle against")
	ErrNoReservation = errors.New("q2d: no reservation to settle")
)

// Record commits an exchange and settles its capacity debit — P-004 §4.6, issue 5.
//
// # One call, because two could be separated by a caller
//
// §4.6's reason for a single call is that a caller holding two could interleave
// them, apply one and not the other, or forget the second. One call cannot be
// separated by a caller. It can still be separated by a crash, and the rest of
// this is about which side of that this file falls.
//
// # Settle first
//
// §4.6 gives the two orders and their crash consequences: debit-then-cache
// over-charges on retry, cache-then-debit under-charges, and an atomic commit does
// neither. Where atomicity is not on offer it says which to take — debit first,
// because over-charging is conservative and under-charging means more disclosure
// than policy intended, which is what Q2D-C-09 rests on.
//
// Atomicity is a property of the stores rather than of this function, and P-008's
// resolved open question 3 makes them one store for exactly this reason: two
// stores would need a distributed transaction, which P-013 §4.6 declines to solve.
// So the atomic row is the one this system takes, and it is reached by a caller
// implementing Budget over the store the cache lives in — at which point both
// writes are in one transaction and this order stops mattering. Nothing here
// changes.
//
// Until that store exists the sink is a parameter and the cache is in memory, so
// the order is doing real work, and it is §4.6's: settle, then write. Given
// Budget's contract that an error means nothing was committed, no state exists in
// which a cache entry was committed and its debit was not.
//
// # What it does not do
//
// It does not call Check. Step 9 decides whether to proceed and this commits what
// the outcome turned out to be; folding the two together would put the lookup and
// the commit either side of the whole of steps 10-17, which is not one operation.
//
// It does not release a reservation it failed to settle, and does not retry. What
// becomes of one is P-008's and P-010 §4.7's.
func (c *ReplayCache) Record(budget Budget, policy FreshnessPolicy, principal, queryID, nonce, requestDigest string, responseBytes []byte, expiresAt int64, reservation Reservation) error {
	// A nil interface value is its own case, not a caller convenience meaning "no
	// budget" or "nothing to settle". Committing an entry against neither is the
	// under-charge this function exists to prevent, so both are refused rather
	// than skipped.
	if budget == nil {
		return ErrNoBudget
	}
	if reservation == nil {
		return ErrNoReservation
	}
	if err := budget.Settle(reservation); err != nil {
		return err
	}
	c.insert(policy, principal, queryID, requestDigest, responseBytes, nonce, expiresAt)
	return nil
}
