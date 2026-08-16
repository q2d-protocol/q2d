//! The replay cache's store — P-004 issue 2.
//!
//! Key and value are P-004 §4.2's. Retention is
//! [`freshness.md`](../spec/freshness.md) §1's, and is **an instant rather than
//! a duration**, which this module takes from
//! [`crate::freshness::FreshnessPolicy::retain_through`] rather than computing.
//!
//! ## What is here and what is not
//!
//! The two indexes, and [`ReplayCache::check`] — step 9's **four-way** outcome
//! over them: fresh, replay, `query_id` reuse, nonce reuse. The decision lives
//! with the indexes rather than above them because it is a reading of both, and
//! a caller assembling it from [`ReplayCache::get`] and
//! [`ReplayCache::nonce_use`] would be the second place the order of those two
//! lookups is decided — which is the part §5.2.1 constrains.
//!
//! **Not here:** the **atomic commit with the capacity debit**, which is P-004
//! issue 5, and **when** step 9 runs, which is the pipeline's and is issue 7.
//!
//! ## Two indexes, because §5.2.1 names two identifiers
//!
//! `core-model.md` §5.2.1 rejects *"a `query_id` **or nonce** reused over
//! different content"*. The `query_id` half is the primary key and the digest
//! comparison; the **nonce** half needs its own index, because a nonce reused
//! under a *new* `query_id` shares no key with its first use.
//!
//! [E-50](../docs/open-escalations.md) settled that, against a recommendation to
//! read the sentence loosely and amend it. Two arguments carried it: the
//! specification governs, so *"the implementation does not do this"* is not
//! evidence the specification is wrong — and at 128 bits from a CSPRNG a
//! collision is negligible, so the only traffic this index refuses is a
//! requester bug.
//!
//! **The nonce index is scoped to the requester**, exactly as the primary key
//! is. A global index would let any requester exhaust another's nonce values and
//! deny them service — a denial-of-service handed to every peer in exchange for
//! nothing.
//!
//! ## Only authenticated requests reach it
//!
//! `core-model.md` §4 places the replay check at step 9, after signature
//! verification at step 4, so nothing unauthenticated can create an entry. That
//! is what makes §1's retention bound sufficient to bound the cache: an attacker
//! without a valid key cannot fill it, and one *with* a valid key is bounded by
//! the validity window.
//!
//! Nothing in this module enforces that ordering — a caller could insert at any
//! point — and P-004 issue 7 is the assertion that the pipeline does not.

use crate::freshness::FreshnessPolicy;
use std::collections::BTreeMap;

/// One cached exchange. P-004 §4.2's value.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    /// Over the exact `signed` bytes received. Compared on lookup, never keyed
    /// on — P-004 §9 item 2.
    pub request_digest: String,
    /// The response as it was sent. **Bytes, not a decision** (§4.5): a replay
    /// returns these unchanged rather than re-evaluating, so two retries cannot
    /// differ and an escalated outcome cannot become an answer.
    pub response_bytes: Vec<u8>,
    /// The instant this entry must be retained **through**, inclusive.
    retain_through: i64,
    /// The nonce this exchange used, so that replacing the entry can retire the
    /// nonce record it wrote. Not public: it exists to keep the two indexes
    /// consistent, not to be read.
    nonce: String,
}

impl Entry {
    /// The retention instant, for tests and operator tooling.
    pub fn retain_through(&self) -> i64 {
        self.retain_through
    }
}

/// What a nonce this requester has already used was attached to.
///
/// Only the digest and the retention instant: this index answers *has this
/// requester used this nonce, and over what content*, and a response body here
/// would be a second copy of one the primary index already holds.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NonceUse {
    /// The digest of the request that used it.
    pub request_digest: String,
    retain_through: i64,
}

impl NonceUse {
    pub fn retain_through(&self) -> i64 {
        self.retain_through
    }
}

/// The store.
///
/// `BTreeMap` rather than `HashMap`: nothing here reaches an output today, and
/// the day something enumerates entries — an operator command, a metric, a test
/// — a hash order would make it depend on a seed. The cost is a comparison per
/// level and the benefit is that the question never arises.
#[derive(Debug, Default)]
pub struct ReplayCache {
    entries: BTreeMap<(String, String), Entry>,
    nonces: BTreeMap<(String, String), NonceUse>,
}

impl ReplayCache {
    pub fn new() -> Self {
        Self::default()
    }

    /// Record an exchange.
    ///
    /// `expires_at` is the request's, in seconds, and the retention instant is
    /// derived from it by `policy` — this module never computes a duration. An
    /// entry for a key already present is replaced, which is the caller's
    /// decision to have made: issue 3 decides whether a second request under one
    /// `query_id` is a replay or a rejection, and by the time it inserts it has
    /// already decided.
    pub fn insert(
        &mut self,
        policy: &FreshnessPolicy,
        principal: &str,
        query_id: &str,
        request_digest: &str,
        response_bytes: Vec<u8>,
        nonce: &str,
        expires_at: i64,
    ) {
        let retain_through = policy.retain_through(expires_at);
        // Both indexes are written in one call and expire at one instant, so
        // there is no state in which a request is remembered by one and not the
        // other. Two insert functions would make that state reachable.
        //
        // **Including on replace**, which review found this had not handled: an
        // entry overwritten under one `query_id` with a different nonce used to
        // leave its first nonce remembered with nothing pointing at it. That
        // failed restrictive — the stale record would reject a later reuse — and
        // the comment above was false, which is worse than the leak.
        //
        // Nothing in the pipeline replaces an entry: issue 3 decides fresh,
        // replay or reuse *before* inserting, and a fresh request carries a new
        // identifier. The invariant is held here anyway, because a store whose
        // documented invariant depends on its caller's discipline does not have
        // one.
        if let Some(previous) = self.entries.get(&(principal.to_string(), query_id.to_string()))
        {
            if previous.nonce != nonce {
                self.nonces
                    .remove(&(principal.to_string(), previous.nonce.clone()));
            }
        }
        self.entries.insert(
            (principal.to_string(), query_id.to_string()),
            Entry {
                request_digest: request_digest.to_string(),
                response_bytes,
                retain_through,
                nonce: nonce.to_string(),
            },
        );
        self.nonces.insert(
            (principal.to_string(), nonce.to_string()),
            NonceUse {
                request_digest: request_digest.to_string(),
                retain_through,
            },
        );
    }

    /// What this requester last used `nonce` for, as of `now`.
    ///
    /// `None` means it has not used it inside the retention window. A caller
    /// comparing the returned digest against the request in hand gets §5.2.1's
    /// distinction: **equal** is the same request arriving again, which the
    /// primary index will report as a retry, and **different** is the nonce
    /// reused over different content, which is a rejection.
    ///
    /// It reports rather than concludes, and [`ReplayCache::check`] is what
    /// draws the conclusion — kept separate so that a caller needing to know
    /// *whether a nonce has been seen* does not have to run the whole of step 9
    /// to find out.
    pub fn nonce_use(&self, principal: &str, nonce: &str, now: i64) -> Option<&NonceUse> {
        self.nonces
            .get(&(principal.to_string(), nonce.to_string()))
            .filter(|use_| now <= use_.retain_through)
    }

    /// Look up an exchange, as of `now`.
    ///
    /// **Retention is applied here and not only by [`Self::evict`]**, so a
    /// caller sees the same answer whether or not eviction has run. A store
    /// whose answers depended on when a sweep last happened would make
    /// idempotency depend on a timer.
    ///
    /// Inclusive: an entry is returned *at* its retention instant, because
    /// `freshness.md` §2 still accepts the request then. An entry that stopped
    /// being visible one second early would let a retry through as fresh —
    /// which debits twice, and is the defect that boundary exists to close.
    pub fn get(&self, principal: &str, query_id: &str, now: i64) -> Option<&Entry> {
        self.entries
            .get(&(principal.to_string(), query_id.to_string()))
            .filter(|entry| now <= entry.retain_through)
    }

    /// Drop every entry whose request can no longer be accepted.
    ///
    /// Strictly past the retention instant, matching [`Self::get`]. Returns how
    /// many were removed, so that eviction is **observable in a test rather
    /// than inferred** — P-004 issue 2 asks for exactly that, because a sweep
    /// that silently did nothing looks identical to one that worked.
    /// Both indexes, because both are bounded by the same instant and an
    /// eviction that swept one would leave the other unbounded — which is the
    /// memory argument `freshness.md` §1 makes, applied to the index that was
    /// added after it.
    pub fn evict(&mut self, now: i64) -> usize {
        let before = self.entries.len() + self.nonces.len();
        self.entries.retain(|_, entry| now <= entry.retain_through);
        self.nonces.retain(|_, use_| now <= use_.retain_through);
        before - (self.entries.len() + self.nonces.len())
    }

    /// How many entries are held. For tests and operator tooling.
    ///
    /// Counts entries that are still stored, including any past their retention
    /// instant that [`Self::evict`] has not yet swept. [`Self::get`] will not
    /// return those, and the difference is deliberate: this is a memory
    /// question and `get` is a protocol one.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// How many nonce records are held.
    ///
    /// Separate from [`Self::len`] rather than summed into it: they are written
    /// together and evicted together, so a test that could only see a total
    /// could not tell a store that dropped one index from a store that dropped
    /// both.
    pub fn nonce_len(&self) -> usize {
        self.nonces.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty() && self.nonces.is_empty()
    }
}

/// What step 9 concluded — P-004 §4.2, extended to four cases by
/// [E-50](../docs/open-escalations.md).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Replay {
    /// No record of this exchange. Proceed.
    Fresh,
    /// The same request arriving again. **The stored bytes, verbatim** — P-004
    /// §4.5, and issue 6: not re-evaluated and not re-signed, because re-signing
    /// regenerates `decided_at` and two retries would differ. That difference
    /// tells a requester the responder re-evaluated, which under opaque
    /// escalation is the state transition `core-model.md` §5.3 forbids
    /// revealing.
    Replayed(Vec<u8>),
    /// An identifier reused over different content. Reject.
    Rejected(ReplayRejection),
}

/// Why step 9 refused.
///
/// **A separate type from [`crate::Rejected`], and the reason is not tidiness.**
/// Every reason in that type maps to a wire value fixed by `core-model.md`
/// §5.2.1's table. These two do not: §5.2.1 gives everything from step 9 onward
/// the value the responder's **pinned registry** declares — `denial_normalization`,
/// which is `unavailable` in the reference manifest and is *data*. A constant
/// here would be one deployment's configuration compiled into every deployment.
///
/// So this type reports the internal reason and the step, and says nothing about
/// the wire. P-009 builds the response and reads the registry.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReplayRejection {
    /// Same `query_id`, different content — P-004 §4.2's third row.
    ///
    /// A decision rather than a fallout: it could be a requester retrying after
    /// correcting a contract, or an attacker probing for cache confusion.
    /// Rejecting makes one `query_id` mean one exchange, and a requester needing
    /// to correct a request issues a new identifier.
    QueryIdReuse,
    /// Same nonce, different content, under a different `query_id` — E-50.
    NonceReuse,
}

impl ReplayRejection {
    /// The corpus's name for this reason.
    pub fn internal_reason(&self) -> &'static str {
        match self {
            ReplayRejection::QueryIdReuse => "query_id_reuse",
            ReplayRejection::NonceReuse => "nonce_reuse",
        }
    }

    /// `core-model.md` §4's step. Always 9.
    ///
    /// A function rather than a constant so that the corpus reads it the same
    /// way it reads every other step, and so a reason added at 9a does not have
    /// to become a second mechanism.
    pub fn step(&self) -> &'static str {
        "9"
    }
}

impl ReplayCache {
    /// `core-model.md` §4 step 9, over both indexes.
    ///
    /// ## Order, and why it is this one
    ///
    /// The `query_id` index first. A genuine retry matches there, and its nonce
    /// record necessarily matches too — so consulting the nonce index first
    /// would have to special-case the retry to avoid rejecting it, and a rule
    /// with an exception carved out for the common case is a rule waiting to be
    /// got wrong.
    ///
    /// ## The case that cannot happen, and is handled anyway
    ///
    /// A nonce record whose digest *equals* the request's, reached after the
    /// `query_id` index found nothing, is a contradiction: equal digests mean
    /// equal signed bytes, and `query_id` is inside those bytes, so the primary
    /// index would have found it. It is treated as a rejection rather than
    /// waved through, because the alternative is deciding that an impossible
    /// state is safe.
    pub fn check(
        &self,
        principal: &str,
        query_id: &str,
        nonce: &str,
        request_digest: &str,
        now: i64,
    ) -> Replay {
        if let Some(entry) = self.get(principal, query_id, now) {
            if entry.request_digest == request_digest {
                return Replay::Replayed(entry.response_bytes.clone());
            }
            return Replay::Rejected(ReplayRejection::QueryIdReuse);
        }
        if self.nonce_use(principal, nonce, now).is_some() {
            return Replay::Rejected(ReplayRejection::NonceReuse);
        }
        Replay::Fresh
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const EXPIRES: i64 = 1_000_300;

    fn cache() -> (ReplayCache, FreshnessPolicy) {
        (ReplayCache::new(), FreshnessPolicy::default())
    }

    fn insert(cache: &mut ReplayCache, policy: &FreshnessPolicy, query_id: &str) {
        cache.insert(
            policy,
            "did:key:z6MkRequesterPrincipal",
            query_id,
            "sha256:aa",
            b"response".to_vec(),
            &format!("nonce-for-{query_id}"),
            EXPIRES,
        );
    }

    #[test]
    fn an_entry_is_returned_verbatim() {
        let (mut cache, policy) = cache();
        insert(&mut cache, &policy, "urn:uuid:one");
        let entry = cache
            .get("did:key:z6MkRequesterPrincipal", "urn:uuid:one", EXPIRES)
            .expect("present");
        assert_eq!(entry.response_bytes, b"response");
        assert_eq!(entry.request_digest, "sha256:aa");
    }

    #[test]
    fn the_key_is_the_principal_and_the_query_id() {
        // Both halves. One requester's identifier must not reach another's
        // entry, and a second identifier from the same requester is a different
        // exchange.
        let (mut cache, policy) = cache();
        insert(&mut cache, &policy, "urn:uuid:one");
        assert!(cache.get("did:key:z6MkSomeoneElse", "urn:uuid:one", EXPIRES).is_none());
        assert!(cache
            .get("did:key:z6MkRequesterPrincipal", "urn:uuid:two", EXPIRES)
            .is_none());
    }

    #[test]
    fn retention_is_inclusive_at_the_instant() {
        // The boundary E-49's review found. An entry visible until `retain_through`
        // and not at it is evicted one second early, and `freshness.md` §2 still
        // accepts the request then — so the retry arrives as fresh and debits
        // again.
        let (mut cache, policy) = cache();
        insert(&mut cache, &policy, "urn:uuid:one");
        let through = policy.retain_through(EXPIRES);
        assert!(cache.get("did:key:z6MkRequesterPrincipal", "urn:uuid:one", through).is_some());
        assert!(cache
            .get("did:key:z6MkRequesterPrincipal", "urn:uuid:one", through + 1)
            .is_none());
    }

    #[test]
    fn the_cache_never_hides_an_entry_the_freshness_check_would_accept() {
        // The relationship rather than the numbers, across every window a
        // request may carry. This is the invariant the two modules share: if
        // §2 accepts, the entry is visible.
        let policy = FreshnessPolicy::default();
        for window in 1..=300 {
            let (issued, expires) = (1_000_000, 1_000_000 + window);
            let mut cache = ReplayCache::new();
            cache.insert(&policy, "p", "q", "sha256:aa", vec![], "n", expires);
            for now in (issued - 120)..=(expires + 120) {
                let acceptable = policy.check(issued, expires, now).is_ok();
                let visible = cache.get("p", "q", now).is_some();
                assert!(
                    !acceptable || visible,
                    "window {window}, now {now}: acceptable and not visible"
                );
            }
        }
    }

    #[test]
    fn eviction_is_observable_and_strictly_past_the_instant() {
        // P-004 issue 2 asks for eviction observable in a test rather than
        // inferred, so `evict` reports a count: a sweep that silently did
        // nothing looks identical to one that worked.
        let (mut cache, policy) = cache();
        insert(&mut cache, &policy, "urn:uuid:one");
        insert(&mut cache, &policy, "urn:uuid:two");
        let through = policy.retain_through(EXPIRES);
        assert_eq!(cache.evict(through), 0, "still acceptable at the instant");
        assert_eq!(cache.len(), 2);
        // Four: two entries and their two nonce records, which expire together
        // because they were written together.
        assert_eq!(cache.evict(through + 1), 4);
        assert_eq!(cache.len(), 0);
        assert_eq!(cache.nonce_len(), 0);
        assert!(cache.is_empty());
    }

    #[test]
    fn lookup_does_not_depend_on_whether_a_sweep_has_run() {
        // Retention is applied on read as well as by the sweep. A store whose
        // answers depended on a timer would make idempotency depend on one.
        let (mut cache, policy) = cache();
        insert(&mut cache, &policy, "urn:uuid:one");
        let after = policy.retain_through(EXPIRES) + 1;
        assert!(cache.get("did:key:z6MkRequesterPrincipal", "urn:uuid:one", after).is_none());
        assert_eq!(cache.len(), 1, "still stored, and not visible");
        cache.evict(after);
        assert!(cache.get("did:key:z6MkRequesterPrincipal", "urn:uuid:one", after).is_none());
    }

    #[test]
    fn a_nonce_is_found_under_a_different_query_id() {
        // The case the primary index cannot see, and the whole of E-50. A nonce
        // reused under a new identifier shares no key with its first use, so
        // without this index the second request is fresh.
        let (mut cache, policy) = cache();
        cache.insert(&policy, "p", "urn:uuid:one", "sha256:aa", vec![], "N", EXPIRES);
        assert!(
            cache.get("p", "urn:uuid:two", EXPIRES).is_none(),
            "the primary index cannot see it"
        );
        let reuse = cache.nonce_use("p", "N", EXPIRES).expect("the nonce index can");
        assert_eq!(reuse.request_digest, "sha256:aa");
    }

    #[test]
    fn the_nonce_index_is_scoped_to_the_requester() {
        // A global index would let any requester exhaust another's nonce values
        // and deny them service.
        let (mut cache, policy) = cache();
        cache.insert(&policy, "p", "q", "sha256:aa", vec![], "N", EXPIRES);
        assert!(cache.nonce_use("someone-else", "N", EXPIRES).is_none());
    }

    #[test]
    fn the_store_reports_the_digest_and_takes_no_view() {
        // §5.2.1's distinction is the caller's to draw: an equal digest is the
        // same request arriving again, a different one is the reuse. A store
        // that decided would be a second place the rule lives — which is why
        // this returns what it recorded rather than a verdict.
        let (mut cache, policy) = cache();
        cache.insert(&policy, "p", "q", "sha256:aa", vec![], "N", EXPIRES);
        let recorded = cache.nonce_use("p", "N", EXPIRES).unwrap();
        assert_eq!(recorded.request_digest, "sha256:aa");
        assert_ne!(recorded.request_digest, "sha256:bb");
    }

    #[test]
    fn both_indexes_expire_at_the_same_instant() {
        // Written together and evicted together, so no state exists in which a
        // request is remembered by one and not the other.
        let (mut cache, policy) = cache();
        cache.insert(&policy, "p", "q", "sha256:aa", vec![], "N", EXPIRES);
        let through = policy.retain_through(EXPIRES);
        assert!(cache.get("p", "q", through).is_some());
        assert!(cache.nonce_use("p", "N", through).is_some());
        assert!(cache.get("p", "q", through + 1).is_none());
        assert!(cache.nonce_use("p", "N", through + 1).is_none());
    }

    #[test]
    fn the_four_outcomes() {
        let (mut cache, policy) = cache();
        // Fresh: nothing recorded.
        assert_eq!(cache.check("p", "q1", "n1", "sha256:aa", EXPIRES), Replay::Fresh);

        cache.insert(&policy, "p", "q1", "sha256:aa", b"answer".to_vec(), "n1", EXPIRES);

        // Replay: same identifier, same content.
        assert_eq!(
            cache.check("p", "q1", "n1", "sha256:aa", EXPIRES),
            Replay::Replayed(b"answer".to_vec())
        );
        // Identifier reuse: same `query_id`, different content.
        assert_eq!(
            cache.check("p", "q1", "n1", "sha256:bb", EXPIRES),
            Replay::Rejected(ReplayRejection::QueryIdReuse)
        );
        // Nonce reuse: new identifier, nonce already used. E-50's case, and the
        // one the primary index alone cannot see.
        assert_eq!(
            cache.check("p", "q2", "n1", "sha256:bb", EXPIRES),
            Replay::Rejected(ReplayRejection::NonceReuse)
        );
        // And a wholly new request is still fresh.
        assert_eq!(cache.check("p", "q2", "n2", "sha256:bb", EXPIRES), Replay::Fresh);
    }

    #[test]
    fn a_retry_is_a_replay_and_not_a_nonce_reuse() {
        // Why the `query_id` index is consulted first. A genuine retry matches
        // both indexes, so a nonce-first order would have to special-case it —
        // and a rule with an exception carved out for the common case is a rule
        // waiting to be got wrong.
        let (mut cache, policy) = cache();
        cache.insert(&policy, "p", "q", "sha256:aa", b"answer".to_vec(), "n", EXPIRES);
        assert!(cache.nonce_use("p", "n", EXPIRES).is_some(), "both indexes match");
        assert_eq!(
            cache.check("p", "q", "n", "sha256:aa", EXPIRES),
            Replay::Replayed(b"answer".to_vec())
        );
    }

    #[test]
    fn a_replay_returns_the_bytes_that_were_stored() {
        // Issue 6. Not re-evaluated and not re-signed: re-signing regenerates
        // `decided_at`, two retries would differ, and that difference tells a
        // requester the responder re-evaluated — which under opaque escalation
        // is what §5.3 forbids revealing.
        let (mut cache, policy) = cache();
        cache.insert(&policy, "p", "q", "sha256:aa", b"exactly these".to_vec(), "n", EXPIRES);
        let first = cache.check("p", "q", "n", "sha256:aa", EXPIRES);
        let second = cache.check("p", "q", "n", "sha256:aa", EXPIRES);
        assert_eq!(first, second, "two retries differ");
        assert_eq!(first, Replay::Replayed(b"exactly these".to_vec()));
    }

    #[test]
    fn an_expired_entry_makes_the_request_fresh_again() {
        // Both indexes stop answering at the same instant, so a request past
        // retention is fresh rather than half-remembered. It cannot actually
        // reach step 9 — §2 rejects it at step 6 — and the store does not rely
        // on that, because a store that depended on a caller checking first
        // would be a store with an undocumented precondition.
        let (mut cache, policy) = cache();
        cache.insert(&policy, "p", "q", "sha256:aa", vec![], "n", EXPIRES);
        let after = policy.retain_through(EXPIRES) + 1;
        assert_eq!(cache.check("p", "q", "n", "sha256:aa", after), Replay::Fresh);
    }

    #[test]
    fn the_two_rejections_are_told_apart_internally_and_share_a_step() {
        // The wire value is deliberately absent from this type: §5.2.1 gives
        // everything from step 9 onward the value the responder's *pinned
        // registry* declares, which is data. A constant here would compile one
        // deployment's configuration into every deployment.
        let reasons = [ReplayRejection::QueryIdReuse, ReplayRejection::NonceReuse];
        let internal: std::collections::BTreeSet<_> =
            reasons.iter().map(|r| r.internal_reason()).collect();
        assert_eq!(internal.len(), 2, "an operator cannot tell them apart");
        assert!(reasons.iter().all(|r| r.step() == "9"));
    }

    #[test]
    fn replacing_an_entry_retires_the_nonce_it_replaced() {
        // Review found this: the two indexes could diverge on replace, leaving a
        // nonce remembered with nothing pointing at it. Nothing in the pipeline
        // replaces an entry, and a documented invariant that depends on the
        // caller's discipline is not one.
        let (mut cache, policy) = cache();
        cache.insert(&policy, "p", "q", "sha256:aa", vec![], "first", EXPIRES);
        cache.insert(&policy, "p", "q", "sha256:bb", vec![], "second", EXPIRES);
        assert!(cache.nonce_use("p", "first", EXPIRES).is_none(), "retired");
        assert!(cache.nonce_use("p", "second", EXPIRES).is_some());
        assert_eq!(cache.nonce_len(), 1, "one exchange, one nonce record");
        // And replacing with the *same* nonce keeps it, rather than deleting the
        // record it is about to write.
        cache.insert(&policy, "p", "q", "sha256:cc", vec![], "second", EXPIRES);
        assert_eq!(
            cache.nonce_use("p", "second", EXPIRES).unwrap().request_digest,
            "sha256:cc"
        );
    }

    #[test]
    fn a_shorter_configured_window_shortens_retention() {
        // Configuration may only make a responder stricter, and retention is
        // derived — so a tighter skew produces a shorter retention without this
        // module knowing anything about configuration.
        let strict = FreshnessPolicy::from_config(Some(5), None, None).unwrap();
        let mut cache = ReplayCache::new();
        cache.insert(&strict, "p", "q", "sha256:aa", vec![], "n", EXPIRES);
        assert!(cache.get("p", "q", EXPIRES + 5).is_some());
        assert!(cache.get("p", "q", EXPIRES + 6).is_none());
    }
}
