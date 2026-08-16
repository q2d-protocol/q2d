//! Q2D reference implementation.
//!
//! A transport-neutral protocol for policy-bound, least-disclosure answers over
//! data held by a participating custodian. See <https://q2d.dev>.
//!
//! Nothing here is usable as a protocol yet. What exists is
//! [`P-002`]'s message layer, built bottom-up: the value model and the
//! deterministic production serializer.
//!
//! [`P-002`]: https://github.com/q2d-protocol/q2d/blob/main/docs/prds/P-002-message-envelope.md

pub mod base64url;
pub mod digest;
pub mod ed25519;
pub mod envelope;
pub mod freshness;
pub mod jws;
pub mod keys;
pub mod parse;
pub mod policy;
pub mod registry;
pub mod replay;
pub mod routing;
pub mod suites;
pub mod timestamp;
pub mod value;
pub mod verify;
pub mod version;

pub use digest::digest;
pub use ed25519::{verify, PrivateKey, PublicKey, SignatureInvalid};
pub use envelope::{parse_envelope, Envelope};
pub use jws::{sign, SignError};
pub use keys::{FixedKeys, KeyResolver};
pub use parse::{parse, ParseError};
pub use policy::{PolicyError, SuitePolicy, DEFAULT_ACCEPTABLE};
pub use routing::{check_routing, project_routing, Routing, RoutingMismatch};
pub use suites::{RegistryError, SuiteEntry, SuiteRegistry, SuiteStatus};
pub use value::{serialize, serialize_operation_data, ProfileError, Value};
pub use verify::{verify_query, Rejected};
pub use version::{check_version, VersionProblem, SUPPORTED};
