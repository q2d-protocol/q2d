//! The replay cache's store — P-004 issue 2.
//!
//! Key and value are P-004 §4.2's. Retention is
//! [`freshness.md`](../spec/freshness.md) §1's, and is **an instant rather than
//! a duration**, which this module takes from
//! [`crate::freshness::FreshnessPolicy::retain_through`] rather than computing.
//!
//! ## What is here and what is not
//!
//! The store: insert, look up, evict. The **three-way outcome** — replay, fresh,
//! identifier reuse — is P-004 issue 3, and the **atomic commit with the
//! capacity debit** is issue 5. Both sit above this and neither is a reason to
//! give the store an opinion: a store that decided whether a digest matched
//! would be a second place the idempotency rule lives.
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
}

impl Entry {
    /// The retention instant, for tests and operator tooling.
    pub fn retain_through(&self) -> i64 {
        self.retain_through
    }
}

/// The store.
///
/// A `BTreeMap` rather than a `HashMap`: nothing here reaches an output today,
/// and the day something enumerates entries — an operator command, a metric, a
/// test — a hash order would make it depend on a seed. The cost is a comparison
/// per level and the benefit is that the question never arises.
#[derive(Debug, Default)]
pub struct ReplayCache {
    entries: BTreeMap<(String, String), Entry>,
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
        expires_at: i64,
    ) {
        self.entries.insert(
            (principal.to_string(), query_id.to_string()),
            Entry {
                request_digest: request_digest.to_string(),
                response_bytes,
                retain_through: policy.retain_through(expires_at),
            },
        );
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
    pub fn evict(&mut self, now: i64) -> usize {
        let before = self.entries.len();
        self.entries.retain(|_, entry| now <= entry.retain_through);
        before - self.entries.len()
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

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
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
        cache.insert(policy, "did:key:z6MkRequesterPrincipal", query_id, "sha256:aa", b"response".to_vec(), EXPIRES);
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
            cache.insert(&policy, "p", "q", "sha256:aa", vec![], expires);
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
        assert_eq!(cache.evict(through + 1), 2);
        assert_eq!(cache.len(), 0);
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
    fn a_shorter_configured_window_shortens_retention() {
        // Configuration may only make a responder stricter, and retention is
        // derived — so a tighter skew produces a shorter retention without this
        // module knowing anything about configuration.
        let strict = FreshnessPolicy::from_config(Some(5), None, None).unwrap();
        let mut cache = ReplayCache::new();
        cache.insert(&strict, "p", "q", "sha256:aa", vec![], EXPIRES);
        assert!(cache.get("p", "q", EXPIRES + 5).is_some());
        assert!(cache.get("p", "q", EXPIRES + 6).is_none());
    }
}
