//! Freshness, skew, and the nonce floor — [`freshness.md`](../spec/freshness.md).
//!
//! P-004 issues 1 and 4. Two checks that happen at different steps and are here
//! together because one document states both: the nonce floor at
//! `core-model.md` §4 step 5, freshness at step 6.
//!
//! ## Nothing here reads a clock
//!
//! `now` is a parameter. A responder's clock is the caller's to supply, which is
//! what lets a corpus vector state it (P-001 §4.3) and what stops two runs of
//! one vector disagreeing. A function here that called a clock could not be
//! pinned by a vector at all, and the boundary cases are exactly where the two
//! implementations have to agree.
//!
//! ## Why the comparisons are integers
//!
//! Timestamps become seconds ([`crate::timestamp::to_epoch_seconds`]) and every
//! comparison is integer. `freshness.md` §2 states the conditions as strict
//! inequalities on exact instants, and a floating-point second would make
//! "exactly at the boundary" depend on rounding.

use crate::timestamp;
use crate::verify::Rejected;
use std::fmt;

/// `freshness.md` §1's clock-skew tolerance, in seconds.
pub const SKEW_SECONDS: i64 = 60;

/// `freshness.md` §1's maximum validity window, in seconds.
pub const MAX_WINDOW_SECONDS: i64 = 300;

/// `freshness.md` §1's minimum `nonce` length, in **decoded** bytes.
///
/// On the decoded bytes and not on the string. Sixteen bytes is twenty-two
/// base64url characters, so a check against the string would accept a twelve-byte
/// nonce — §3 states which, because the two differ and nothing in a message says
/// which a responder applied.
pub const MIN_NONCE_BYTES: usize = 16;

/// Why a policy could not be built. Startup fails on one of these.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PolicyError(String);

impl fmt::Display for PolicyError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for PolicyError {}

/// The bounds this responder applies.
///
/// **Configuration may only make a responder stricter** — `freshness.md` §1 —
/// and a value on the wrong side of a bound fails at startup rather than being
/// clamped. Same rule and same reason as [`crate::SuitePolicy`]: a clamped
/// misconfiguration reads as success, and the operator's belief that they
/// configured something survives until the day it matters.
#[derive(Debug, Clone, Copy)]
pub struct FreshnessPolicy {
    skew: i64,
    window: i64,
    min_nonce_bytes: usize,
}

impl Default for FreshnessPolicy {
    /// The specification's bounds, which is what a deployment that configures
    /// nothing gets.
    fn default() -> Self {
        FreshnessPolicy {
            skew: SKEW_SECONDS,
            window: MAX_WINDOW_SECONDS,
            min_nonce_bytes: MIN_NONCE_BYTES,
        }
    }
}

impl FreshnessPolicy {
    /// Build from configuration, refusing anything laxer than the specification.
    ///
    /// Each argument is `None` where an operator configured nothing. The
    /// directions differ per bound and they are not arbitrary: a *smaller* skew
    /// or window is stricter, and a *larger* nonce floor is. That is the shape
    /// `freshness.md` §1's table states, and getting one backwards would let
    /// configuration widen the interval a captured envelope stays replayable in
    /// while looking like tightening.
    pub fn from_config(
        skew: Option<i64>,
        window: Option<i64>,
        min_nonce_bytes: Option<usize>,
    ) -> Result<Self, PolicyError> {
        let skew = skew.unwrap_or(SKEW_SECONDS);
        let window = window.unwrap_or(MAX_WINDOW_SECONDS);
        let min_nonce_bytes = min_nonce_bytes.unwrap_or(MIN_NONCE_BYTES);

        // Named values, because this is the operator's own configuration file
        // and they need to know which line is wrong. Nothing here comes from a
        // message.
        if skew > SKEW_SECONDS {
            return Err(PolicyError(format!(
                "configured clock skew {skew}s is above freshness.md §1's {SKEW_SECONDS}s, \
                 which would accept requests the specification does not"
            )));
        }
        if window > MAX_WINDOW_SECONDS {
            return Err(PolicyError(format!(
                "configured validity window {window}s is above freshness.md §1's \
                 {MAX_WINDOW_SECONDS}s, which would leave a captured envelope replayable \
                 for longer than the specification permits"
            )));
        }
        if min_nonce_bytes < MIN_NONCE_BYTES {
            return Err(PolicyError(format!(
                "configured nonce floor {min_nonce_bytes} bytes is below freshness.md §1's \
                 {MIN_NONCE_BYTES}"
            )));
        }
        if skew < 0 || window <= 0 {
            return Err(PolicyError(
                "a negative skew or a non-positive window would reject every request".into(),
            ));
        }
        Ok(FreshnessPolicy {
            skew,
            window,
            min_nonce_bytes,
        })
    }

    /// The instant a replay-cache entry for this request must be retained
    /// **through** — `freshness.md` §1.
    ///
    /// Inclusive, and that is the whole point of the function existing. §2's
    /// first condition rejects only when `now` is *strictly* past
    /// `expires_at + skew`, so the request is still acceptable at that instant
    /// and an entry evicted then is evicted one second early. Deriving the
    /// instant here rather than letting the cache compute a duration is what
    /// stops the two drifting apart.
    pub fn retain_through(&self, expires_at: i64) -> i64 {
        expires_at + self.skew
    }

    /// `freshness.md` §2, at `core-model.md` §4 step 6.
    ///
    /// Takes seconds, not text: the caller has the verified core object and has
    /// already read its timestamps, and a second parse here would be a second
    /// definition of what a Q2D timestamp is.
    pub fn check(&self, issued_at: i64, expires_at: i64, now: i64) -> Result<(), Rejected> {
        // The window first, because it is a property of the message alone and
        // the other two involve the responder's clock. A message whose window is
        // unusable is wrong however good the clock is, and reporting a clock
        // disagreement for it would send an operator to the wrong place.
        let window = expires_at - issued_at;
        if window <= 0 || window > self.window {
            return Err(Rejected::RequestWindowOutOfRange);
        }
        if now > expires_at + self.skew {
            return Err(Rejected::RequestExpired);
        }
        if now < issued_at - self.skew {
            return Err(Rejected::RequestFutureDated);
        }
        Ok(())
    }

    /// `freshness.md` §3's floor, at `core-model.md` §4 step 5.
    ///
    /// The floor and nothing else. Entropy is the **requester's** obligation and
    /// no check here can establish it — sixteen zero bytes pass this function.
    /// That is not a shortcoming to be fixed later: a responder holds one nonce
    /// and no distribution, so there is nothing to measure.
    pub fn check_nonce(&self, nonce: &str) -> Result<(), Rejected> {
        let decoded = crate::base64url::decode(nonce)
            .map_err(|_| Rejected::CoreObjectNonceNotBase64url)?;
        if decoded.len() < self.min_nonce_bytes {
            return Err(Rejected::CoreObjectNonceTooShort);
        }
        Ok(())
    }
}

/// [`FreshnessPolicy::check`] over the text a core object carries.
///
/// A convenience for a caller holding strings rather than seconds. A timestamp
/// that will not convert is **not** a freshness failure: it is a core object
/// that never satisfied `core-model.md` §2.2, caught at step 5, and reporting it
/// as expired would tell a requester its clock is wrong when its serializer is.
pub fn check_text(
    policy: &FreshnessPolicy,
    issued_at: &str,
    expires_at: &str,
    now: &str,
) -> Result<(), Rejected> {
    let seconds = |text: &str| {
        timestamp::to_epoch_seconds(text).ok_or(Rejected::CoreObjectMalformed)
    };
    policy.check(seconds(issued_at)?, seconds(expires_at)?, seconds(now)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    const ISSUED: i64 = 1_000_000;
    const EXPIRES: i64 = ISSUED + 300;

    fn policy() -> FreshnessPolicy {
        FreshnessPolicy::default()
    }

    #[test]
    fn a_request_inside_its_window_is_fresh() {
        assert_eq!(policy().check(ISSUED, EXPIRES, ISSUED + 1), Ok(()));
    }

    #[test]
    fn both_boundaries_are_inclusive_to_the_second() {
        // §2's comparisons are strict, so the tolerance instants themselves are
        // inside. This is the assertion P-004 §7 asks for, and the one place two
        // implementations most easily disagree while both looking right.
        let p = policy();
        assert_eq!(p.check(ISSUED, EXPIRES, EXPIRES + SKEW_SECONDS), Ok(()));
        assert_eq!(
            p.check(ISSUED, EXPIRES, EXPIRES + SKEW_SECONDS + 1),
            Err(Rejected::RequestExpired)
        );
        assert_eq!(p.check(ISSUED, EXPIRES, ISSUED - SKEW_SECONDS), Ok(()));
        assert_eq!(
            p.check(ISSUED, EXPIRES, ISSUED - SKEW_SECONDS - 1),
            Err(Rejected::RequestFutureDated)
        );
    }

    #[test]
    fn the_window_is_a_range_and_not_a_ceiling() {
        // The lower end is what E-49 added, and it is not decoration: a negative
        // window is above no ceiling, and there is an interval in which the
        // other two conditions both pass. The third case below is inside that
        // interval, so a ceiling-only implementation calls it fresh.
        let p = policy();
        assert_eq!(p.check(ISSUED, ISSUED + 301, ISSUED), Err(Rejected::RequestWindowOutOfRange));
        assert_eq!(p.check(ISSUED, ISSUED, ISSUED), Err(Rejected::RequestWindowOutOfRange));
        assert_eq!(
            p.check(ISSUED, ISSUED - 10, ISSUED),
            Err(Rejected::RequestWindowOutOfRange)
        );
    }

    #[test]
    fn a_negative_window_would_otherwise_be_fresh() {
        // The counterexample `freshness.md` §2 states, executed. With the window
        // condition removed, every `now` across a skew-length interval passes
        // the other two — so this is the interval the range closed, and the test
        // exists to fail if the lower bound is ever dropped.
        let (issued, expires) = (ISSUED, ISSUED - 10);
        let mut would_have_passed = 0;
        for now in (issued - 200)..(issued + 200) {
            let expired = now > expires + SKEW_SECONDS;
            let future = now < issued - SKEW_SECONDS;
            if !expired && !future {
                would_have_passed += 1;
                assert_eq!(
                    policy().check(issued, expires, now),
                    Err(Rejected::RequestWindowOutOfRange),
                    "now={now}"
                );
            }
        }
        assert_eq!(would_have_passed, 111, "the interval §2 describes");
    }

    #[test]
    fn every_freshness_rejection_is_one_wire_value_at_one_step() {
        // §5.2.1 gives `expired` for all three, so a requester cannot tell a
        // clock disagreement from a window it built wrongly. Asserted across the
        // causes rather than per cause — per-case assertions pass while the
        // values diverge.
        let p = policy();
        let rejections = [
            p.check(ISSUED, EXPIRES, EXPIRES + 1000).unwrap_err(),
            p.check(ISSUED, EXPIRES, ISSUED - 1000).unwrap_err(),
            p.check(ISSUED, ISSUED + 1000, ISSUED).unwrap_err(),
        ];
        let internal: std::collections::BTreeSet<_> =
            rejections.iter().map(|r| format!("{r:?}")).collect();
        let external: std::collections::BTreeSet<_> =
            rejections.iter().map(|r| r.external_reason()).collect();
        let steps: std::collections::BTreeSet<_> = rejections.iter().map(|r| r.step()).collect();
        assert_eq!(internal.len(), 3, "an operator cannot tell them apart");
        assert_eq!(external, ["expired"].into_iter().collect());
        assert_eq!(steps, ["6"].into_iter().collect());
    }

    #[test]
    fn retention_is_the_instant_the_request_stops_being_acceptable() {
        // The two have to agree or the cache and the freshness check disagree at
        // exactly one second, which is the defect E-49's review found. Asserted
        // as a relationship rather than as a number.
        let p = policy();
        let through = p.retain_through(EXPIRES);
        assert_eq!(p.check(ISSUED, EXPIRES, through), Ok(()), "still acceptable");
        assert!(p.check(ISSUED, EXPIRES, through + 1).is_err(), "and not after");
    }

    #[test]
    fn an_entry_is_never_retained_beyond_the_derived_bound() {
        // `window + 2×skew` is what the derivation bounds an entry to, which is
        // the memory argument. Checked against the earliest instant the request
        // could have been accepted, not against entry creation.
        let p = policy();
        for window in 1..=MAX_WINDOW_SECONDS {
            let expires = ISSUED + window;
            let earliest_acceptance = ISSUED - SKEW_SECONDS;
            let held = p.retain_through(expires) - earliest_acceptance;
            assert!(
                held <= MAX_WINDOW_SECONDS + 2 * SKEW_SECONDS,
                "window {window} held for {held}"
            );
        }
    }

    #[test]
    fn the_nonce_floor_is_on_decoded_bytes() {
        // Sixteen bytes is twenty-two base64url characters. A check against the
        // string would accept the second of these, which carries twelve bytes.
        let p = policy();
        assert_eq!(p.check_nonce(&crate::base64url::encode(&[0u8; 16])), Ok(()));
        assert_eq!(
            p.check_nonce(&crate::base64url::encode(&[0u8; 12])),
            Err(Rejected::CoreObjectNonceTooShort)
        );
        assert_eq!(
            crate::base64url::encode(&[0u8; 16]).len(),
            22,
            "the length a string check would have compared"
        );
    }

    #[test]
    fn a_nonce_of_zero_bytes_passes_and_that_is_the_point() {
        // `freshness.md` §3: the floor is necessary and not sufficient. This
        // nonce has no entropy at all and there is nothing here that could
        // notice — a responder holds one nonce and no distribution. The test
        // exists so nobody later reads the floor as an entropy check.
        assert_eq!(policy().check_nonce(&crate::base64url::encode(&[0u8; 32])), Ok(()));
    }

    #[test]
    fn a_nonce_that_is_not_base64url_is_a_different_reason() {
        // Two mistakes in a requester's own message: an encoding fault, and a
        // generator asked for too few bytes. One wire value, because both are
        // visible in the bytes the requester produced.
        let p = policy();
        let bad = p.check_nonce("****not base64url****").unwrap_err();
        assert_eq!(bad, Rejected::CoreObjectNonceNotBase64url);
        assert_eq!(bad.external_reason(), "malformed");
        assert_eq!(bad.step(), "5");
    }

    #[test]
    fn configuration_may_only_make_a_responder_stricter() {
        assert!(FreshnessPolicy::from_config(Some(30), Some(120), Some(32)).is_ok());
        // Each direction, because getting one backwards reads as tightening.
        for (skew, window, nonce) in [
            (Some(SKEW_SECONDS + 1), None, None),
            (None, Some(MAX_WINDOW_SECONDS + 1), None),
            (None, None, Some(MIN_NONCE_BYTES - 1)),
        ] {
            assert!(
                FreshnessPolicy::from_config(skew, window, nonce).is_err(),
                "{skew:?} {window:?} {nonce:?}"
            );
        }
    }

    #[test]
    fn a_laxer_configuration_fails_startup_rather_than_being_clamped() {
        // The important half. A clamped misconfiguration reads as success.
        let error = FreshnessPolicy::from_config(None, Some(600), None).unwrap_err();
        assert!(error.to_string().contains("600"), "{error}");
        assert!(error.to_string().contains("300"), "{error}");
    }

    #[test]
    fn an_unreadable_timestamp_is_malformed_and_not_expired() {
        // A spelling §2.2 refuses is a fault in the requester's serializer, and
        // calling it `expired` would send them to their clock.
        let rejected =
            check_text(&policy(), "2026-07-31T09:00:00+00:00", "2026-07-31T09:05:00Z", "2026-07-31T09:01:00Z")
                .unwrap_err();
        assert_eq!(rejected, Rejected::CoreObjectMalformed);
        assert_eq!(rejected.external_reason(), "malformed");
    }

    #[test]
    fn check_text_agrees_with_check() {
        assert_eq!(
            check_text(
                &policy(),
                "2026-07-31T09:00:00Z",
                "2026-07-31T09:05:00Z",
                "2026-07-31T09:06:00Z"
            ),
            Ok(()),
            "one minute past expiry is exactly the skew tolerance"
        );
        assert_eq!(
            check_text(
                &policy(),
                "2026-07-31T09:00:00Z",
                "2026-07-31T09:05:00Z",
                "2026-07-31T09:06:01Z"
            ),
            Err(Rejected::RequestExpired)
        );
    }
}
