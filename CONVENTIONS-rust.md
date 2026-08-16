# Rust conventions

**Scope:** language-specific decisions only. Anything that changes what Q2D
*means* belongs in [`spec/`](spec/); anything that changes how a module is built
and verified belongs in its PRD. If a decision here would make the Rust and Go
implementations behave differently, it is in the wrong document —
[`docs/mvp-scope.md`](docs/mvp-scope.md) §6.

Written at Stage 1, as that section requires, and revised rarely.

---

## 1. The shape of the crate

- **Library first.** `src/lib.rs` exports the protocol modules; `src/bin/` holds
  the conformance runner and nothing else.
- **One module per specification concern**, named for the concern rather than
  for the type: `value`, `parse`, `envelope`, `routing`, `digest`, `base64url`,
  `ed25519`, `version`.
- **Errors are types, not strings**, where a caller branches on them —
  `VersionProblem`, `RoutingMismatch`. Where a caller cannot branch, a single
  opaque type with a `Display` message is correct and preferable:
  `SignatureInvalid` has no variants on purpose, because
  [`core-model.md`](spec/core-model.md) §5.2.1 gives one external class for the
  whole of authentication and four variants invite four responses.
- **No `unsafe`.** There is no line of it today and adding one is a review
  question, not a performance decision.
- **Rust 2021, stable toolchain.** No nightly features.

## 2. Dependency policy

**Default: none.** The crate carried zero dependencies through P-001 and P-002,
and `src/digest.rs`, `src/base64url.rs` and `src/bin/q2d-conform.rs` are
hand-written because of it. That is not frugality for its own sake — this code
is read by people deciding whether to trust a protocol, and every crate in the
tree is something they must decide about separately.

**A dependency is justified when hand-writing it would be worse for
correctness, not when it would be slower to write.** The test:

| Hand-write | Depend |
|---|---|
| A fixed transformation with published known answers, no secrets in the control flow, and failure modes that are all visible in a test — SHA-256, base64url, JSON | Anything where a *correct-looking* implementation can be subtly wrong in a way tests do not reveal — timing behaviour, curve arithmetic, acceptance rules libraries disagree about |

**Today the list is one crate.**

```toml
ed25519-dalek = { version = "3.0", default-features = false }
```

Chosen under [E-47](docs/open-escalations.md). Three things follow from that
decision and are conditions on it, not commentary:

1. **The acceptance rule is pinned, not inherited.** `verify_strict`, never
   `verify`. The difference is not academic: under the permissive rule
   `A = R = identity, S = 0` is a valid signature over *every* message, by
   anyone, with no private key. `src/ed25519.rs` states the four rules Q2D
   accepts a signature under, and a test asserts the permissive rule accepts
   what Q2D refuses.
2. **The criteria are written down where an implementer reads them** —
   [`crypto-suites.md`](spec/crypto-suites.md) §3, which is `spec/` and
   therefore governs, rather than left as "whatever the library does". They
   started in this document and the module headers; Codex was right that a
   third implementation reads `spec/` and would have picked its own edge cases.
3. **A shared fixture holds both implementations to the same answers.**
   [`testdata/ed25519-acceptance.txt`](testdata/README.md) — ten rows: one
   published answer as a control, and nine cases RFC 8032 does not decide.

`default-features = false` drops key *generation*, which needs an RNG and which
Q2D does not do: every key in this repository is a fixed test seed.

**Adding a second dependency is an escalation**, not a commit. So is widening
the feature set of this one.

**`Cargo.lock` is committed**, though this is a library. The usual argument for
omitting it — downstream consumers resolve their own versions — is outweighed
by the one that matters here: a reviewer should be able to check out a commit
and build the exact tree it was reviewed against.

**What does not get a dependency, and why it is not inconsistent:**
`tools/author_vectors.py` hand-rolls Ed25519. The corpus asserts what the
implementations must do, so deriving it from a library either implementation
might also use would make the vectors agree with the code by construction. Its
independence is the point, and its known-answer gate is what makes it safe.

## 3. Testing

- **Unit tests beside the code** in `#[cfg(test)] mod tests`, integration tests
  in `tests/` where they read a fixture or cross a module boundary.
- **Negative cases are not optional.** For this protocol the interesting
  behaviour is what it refuses, and a module whose tests are all positive has
  tested the easy half.
- **A test that passes for the wrong reason is worse than a missing test.**
  This has happened here: a non-ASCII-digit case was rejected by a *length*
  check and never reached the digit check it was written for. Where a case
  could be caught by an earlier rule, assert which rule caught it.
- **Fixtures live in `testdata/`** and are read by both implementations. A rule
  asserted only in Rust is a rule Go can drift from silently.

## 4. Idiom

- `rustfmt` defaults. No configuration file, so there is nothing to disagree
  about.
- Doc comments explain *why*; the signature explains what. A comment restating
  the code is deleted in review.
- Prefer `&[u8]` in interfaces and own bytes internally. `verify` takes a slice
  and checks its length rather than taking `[u8; 64]`, because the caller's
  input arrives from the wire and the length check belongs to the module that
  knows what it means.
- No iteration order may reach an output. `BTreeMap` where order matters —
  though note `BTreeMap`'s order is *not* the serialization profile's, which
  [`serialization.md`](spec/serialization.md) §1 orders by UTF-16 code unit.
  That difference has already caused one divergence in this repository.
