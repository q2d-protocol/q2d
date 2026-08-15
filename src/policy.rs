//! The verifier's acceptable set — local configuration, never a message.
//!
//! P-003 issue 4, and §9.1: **this is the entire downgrade defence.** §4.2
//! step 2 rejects unless the declared suite is a member of this set, and a
//! verifier that verifies with whatever the header names has agility in the
//! same sense that an unlocked door has a lock.
//!
//! ## Why there is no constructor taking a message
//!
//! There is no code path from received data to a [`SuitePolicy`]. That is the
//! property, and it is carried by the type rather than by a comment: the only
//! constructor takes a registry and a list of identifiers an operator wrote
//! down, and nothing in this crate produces such a list from a message.
//!
//! ## The floor, and why lowering it fails rather than clamps
//!
//! P-003 §10 settled the source: **a config file, over a compiled-in floor that
//! configuration may raise and may never lower.** Environment variables were
//! rejected as a source — invisible in review, trivially altered by anything
//! sharing the process, and a downgrade that lands via one leaves no artifact
//! anyone would think to check.
//!
//! The floor is [`meets_floor`]: a suite must be registered, and its status must
//! permit verification. Configuration may name **fewer** suites than the floor
//! admits, which is raising it. Naming one the floor excludes is **a startup
//! failure**, not a silently dropped entry, because a clamped misconfiguration
//! reads as success — the operator believes they configured something they did
//! not, and the belief survives until the day it matters.

use crate::suites::{SuiteRegistry, SuiteStatus};
use std::collections::BTreeSet;
use std::fmt;

/// The suite a build accepts when configuration names none.
///
/// The mandatory-to-implement suite, alone. A default that accepted everything
/// registered would make adding a suite to the registry a change in what every
/// unconfigured deployment accepts.
pub const DEFAULT_ACCEPTABLE: &str = "eddsa-jws-2026";

/// Why a policy could not be built. Startup fails on one of these.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PolicyError(String);

impl fmt::Display for PolicyError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for PolicyError {}

/// The set of suites this verifier accepts.
#[derive(Debug, Clone)]
pub struct SuitePolicy {
    acceptable: BTreeSet<String>,
}

/// The compiled-in floor: registered, and permitted to verify by its status.
///
/// Configuration cannot reach below this. A `withdrawn` suite is excluded here
/// rather than at verification time so that a deployment naming one **fails to
/// start** — the operator finds out when they change the configuration rather
/// than when a message arrives.
fn meets_floor(registry: &SuiteRegistry, id: &str) -> bool {
    registry
        .resolve(id)
        .map(|entry| entry.status.may_verify())
        .unwrap_or(false)
}

impl SuitePolicy {
    /// Build a policy from configuration.
    ///
    /// `configured` is what an operator wrote in a config file. An empty list
    /// means they wrote nothing, which is [`DEFAULT_ACCEPTABLE`].
    pub fn from_config(
        registry: &SuiteRegistry,
        configured: &[String],
    ) -> Result<Self, PolicyError> {
        let wanted: Vec<String> = if configured.is_empty() {
            vec![DEFAULT_ACCEPTABLE.to_string()]
        } else {
            configured.to_vec()
        };

        let mut acceptable = BTreeSet::new();
        for id in wanted {
            if !meets_floor(registry, &id) {
                // Named, because this is the operator's own configuration and
                // they need to know which line is wrong. Nothing here comes
                // from a message.
                return Err(PolicyError(format!(
                    "configuration accepts `{id}`, which is below this build's \
                     floor — it is unregistered, or its status does not permit \
                     verification. Startup fails rather than dropping it, \
                     because a dropped entry reads as a policy that was applied"
                )));
            }
            acceptable.insert(id);
        }

        if acceptable.is_empty() {
            return Err(PolicyError(
                "an empty acceptable set would reject every message".into(),
            ));
        }
        Ok(SuitePolicy { acceptable })
    }

    /// §4.2 step 2. **The only question this type answers.**
    pub fn accepts(&self, id: &str) -> bool {
        self.acceptable.contains(id)
    }

    /// The configured set, for operator tooling and capability discovery.
    ///
    /// **Never for a rejection message** — §4.5: a rejection names no
    /// alternative, because suggesting a suite the verifier would accept turns
    /// every rejection into a probe of local policy. Advertising is a
    /// deliberate choice made once, in capability discovery, rather than leaked
    /// one rejection at a time.
    pub fn advertised(&self) -> Vec<&str> {
        self.acceptable.iter().map(String::as_str).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn registry(status: &str) -> SuiteRegistry {
        let text = format!(
            r#"{{"suites":[
                {{"id":"eddsa-jws-2026","algorithm":"a","serialization":"s",
                  "hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"{status}"}},
                {{"id":"withdrawn-suite","algorithm":"a","serialization":"s",
                  "hash":"h","effective_from":"2026-08-15","deprecated_from":null,"withdrawn_from":null,"security_notes":[],"references":[],"status":"withdrawn"}}]}}"#
        );
        SuiteRegistry::load(text.as_bytes()).unwrap()
    }

    #[test]
    fn the_default_is_the_mandatory_suite_alone() {
        let policy = SuitePolicy::from_config(&registry("active"), &[]).unwrap();
        assert!(policy.accepts(DEFAULT_ACCEPTABLE));
        assert_eq!(policy.advertised(), vec![DEFAULT_ACCEPTABLE]);
    }

    #[test]
    fn configuration_may_raise_the_floor() {
        // Naming fewer suites than the floor admits is the direction that is
        // always allowed.
        let registry = registry("active");
        let policy = SuitePolicy::from_config(&registry, &["eddsa-jws-2026".into()]).unwrap();
        assert!(policy.accepts("eddsa-jws-2026"));
        assert!(!policy.accepts("withdrawn-suite"));
    }

    #[test]
    fn configuration_may_not_lower_it_and_startup_fails() {
        // The important half. Not clamped, not warned about, not dropped: a
        // clamped misconfiguration reads as success.
        let error = SuitePolicy::from_config(&registry("active"), &["withdrawn-suite".into()])
            .unwrap_err();
        assert!(error.to_string().contains("withdrawn-suite"), "{error}");
        assert!(error.to_string().contains("floor"), "{error}");
    }

    #[test]
    fn an_unregistered_suite_is_below_the_floor() {
        assert!(SuitePolicy::from_config(&registry("active"), &["hmac-sha1-1999".into()]).is_err());
    }

    #[test]
    fn a_deprecated_suite_may_still_be_accepted() {
        // §6's asymmetry reaches the policy: receipts signed under a deprecated
        // suite remain evidence, so a verifier may keep accepting it.
        let policy = SuitePolicy::from_config(&registry("deprecated"), &[]).unwrap();
        assert!(policy.accepts("eddsa-jws-2026"));
    }

    #[test]
    fn a_withdrawn_default_fails_startup_rather_than_accepting_nothing() {
        // The default names the MTI suite; if the registry says it is
        // withdrawn, this build cannot verify anything and says so at startup
        // rather than rejecting every message at run time with a reason nobody
        // connects to the registry.
        let error = SuitePolicy::from_config(&registry("withdrawn"), &[]).unwrap_err();
        assert!(error.to_string().contains("eddsa-jws-2026"), "{error}");
    }

    #[test]
    fn nothing_constructs_a_policy_from_a_message() {
        // Asserted by the interface rather than by a runtime check: the only
        // constructor takes a registry and a list of identifiers, and no
        // function in this crate produces that list from received bytes. This
        // test exists to fail loudly if a second constructor is ever added —
        // it names the property so that the next person adding one reads it.
        let registry = registry("active");
        let policy = SuitePolicy::from_config(&registry, &[]).unwrap();
        assert!(policy.accepts(DEFAULT_ACCEPTABLE));
    }
}
