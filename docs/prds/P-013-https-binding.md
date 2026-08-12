# P-013 — Direct HTTPS binding and custodian daemon

| Field | Detail |
|---|---|
| PRD | P-013 |
| Stage | 6 |
| Status | **Ready for decomposition** |
| Size | L |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-009](P-009-denial-normalization.md), [P-010](P-010-responder-pipeline.md), [P-011](P-011-receipts-audit.md), [P-012](P-012-requester-runtime.md), [P-014](P-014-identity-pairing.md) |
| Blocks | P-015, P-016 |
| Pairs with | [P-014](P-014-identity-pairing.md) — the daemon cannot complete the walkthrough without a key resolver, and owns none of it |

---

## 1. Purpose

Put the responder behind an HTTP surface and package it as something a person
can install, configure, and run.

Everything to this point is a library. [`mvp-scope.md`](../mvp-scope.md) §1
requires a custodian on one machine and a requester on another, paired and
exchanging answers by following a published quickstart and nothing else. This
PRD is the difference between a specification that is implementable and one that
has been implemented.

**Claims served.** None, and that is the honest position. Q2D-C-11 is about *two*
bindings preserving identical semantics; with one binding there is nothing to
compare, and [`mvp-scope.md`](../mvp-scope.md) §4 Stage 6 now states a claim of
none for that reason.

**Conformance:** CC-12
([`conformance-classes.md`](../../spec/conformance-classes.md)), added for this
binding. Class conformance and claim coverage are different things, and §4.8
keeps them apart — CC-12 passing does not establish Q2D-C-11.

The binding's job is negative: preserve every semantic the ten modules beneath
it establish, and add nothing. Most of this PRD is about what the transport must
refuse to do.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/scope.md`](../../spec/scope.md) §6 | What a binding must preserve; a binding that drops a field rather than failing is non-conforming |
| [`spec/core-model.md`](../../spec/core-model.md) §2.1 | The envelope the body carries; `routing` is advisory and travels in the clear |
| [`spec/core-model.md`](../../spec/core-model.md) §4 steps 1–2 | Bounded parse before allocation; advisory shedding is never a security decision |
| [`spec/core-model.md`](../../spec/core-model.md) §5.1–5.3 | The three outcomes the transport must carry without partitioning them |
| [`spec/core-model.md`](../../spec/core-model.md) §5.3 | Explicit escalation returns a pending token; opaque escalation returns nothing to poll |
| [`spec/core-model.md`](../../spec/core-model.md) §7 | Idempotency, which the transport must not acquire a second identity for |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-08 | Response, size, and retry semantics identical across causes |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-11 | Equivalence is a property of two bindings |
| [`spec/claims.md`](../../spec/claims.md) Q2D-NC-05 | Timing, size, notification, and rate-limit channels remain |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §4 | Rejection is not negotiation; suites are advertised through capability discovery |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) CC-12 | The class this binding implements; §4.1–4.5 are its must and must-not lists |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) CC-8, CC-9 | The MCP and A2A binding classes — neither is this one, and neither may be claimed here |
| [`threat-model/trust-matrix.md`](../../threat-model/trust-matrix.md) §5 | Network metadata, size, and timing are named residual channels |
| [`docs/mvp-scope.md`](../mvp-scope.md) §1 | The two-machine walkthrough that is this stage's gate |
| [`docs/mvp-scope.md`](../mvp-scope.md) §4 | The Stage 6 endpoint list — three endpoints; the registry-entry endpoint was dropped (§4.3) |
| [`spec/core-model.md`](../../spec/core-model.md) §9.1 | A rate limit is required, and its rejection is a normalized Q2D outcome rather than a transport status — §4.2 |

## 3. Module boundary

**Inside:** the HTTP surface and its exact semantics; status-code and header
policy; transport-level size limits; the daemon — configuration, startup
validation, lifecycle, shutdown; TLS posture; the capability document; access
logging policy; the quickstart's runnable surface.

**Explicitly outside:** every protocol decision. This module calls
[P-010](P-010-responder-pipeline.md)'s `process` and serializes what comes back;
it evaluates nothing, classifies nothing, and signs nothing. Identity, key
resolution, and pairing (**P-014**). Escalation semantics, grants, and approval
scope (**P-015**) — this PRD defines the shape of `GET /pending/{token}` and not
what a token means. The requester side (**P-012**).

**Also outside:** timing normalization. [P-009](P-009-denial-normalization.md)
§4.7 owns the padding hook because the tier is known there and the transport
does not know it. This module must not add a second one, and must not add
gratuitous timing differences of its own — see §4.2.

## 4. Design

### 4.1 The binding decides nothing, and carries nothing

The request body **is** the envelope from
[`core-model.md`](../../spec/core-model.md) §2.1. Nothing is transposed into a
path, a query parameter, or a header, and the daemon reads no Q2D field from
any of them.

This is the whole reason direct HTTPS is the reference binding. There is no
impedance mismatch to resolve: the transport carries an opaque object and hands
it to `process`. A field cannot be dropped because the transport lacks a place
for it — [`scope.md`](../../spec/scope.md) §6's non-conformance condition — since
the transport never unpacks it.

Concretely, and each is an escalate-if-changed decision:

- **No Q2D field appears in any header.** A header carrying one is not merely
  redundant; it is an unsigned copy of a signed value, and the difference
  between them would be undetectable at the point of use. The daemon ignores
  such headers entirely rather than comparing them — comparison is
  [P-002](P-002-message-envelope.md) §4.6's job, on `routing`, after
  verification.
- **No path carries a predicate, a principal, or a query identifier.** A path is
  logged by every proxy on the route. `POST /.well-known/q2d/query` is the same
  string for every exchange.
- **No idempotency key header.** [`core-model.md`](../../spec/core-model.md) §7
  already identifies an exchange, by signed `query_id` and `nonce`. A second
  identifier at the transport layer would be an unsigned one, and two identities
  for one exchange is how a retry becomes a distinct request.

### 4.2 One status code for every signed response

**`answer`, `deny`, and `escalate` all return HTTP 200 with the signed response
in the body.** A request that never became a Q2D exchange — malformed framing,
oversized body, wrong content type, unknown path — returns a 4xx and no signed
body.

The reasoning is [P-009](P-009-denial-normalization.md) reaching the transport
layer. That PRD makes every denial in a class byte-identical; a binding that
returns 403 for a policy denial and 200 for an answer has restored the
distinction one layer up, where it is visible to every intermediary without
unwrapping anything, and where it lands in an ordinary access log by default.

Two consequences follow, and both are load-bearing:

- **No `429`, no `503`, and no `Retry-After` on any Q2D outcome.**
  [`core-model.md`](../../spec/core-model.md) §5.2's response has no field for
  retry metadata, precisely because a value computed from a rate limiter is
  cause-specific by construction. A `Retry-After` header is retry metadata
  wearing a different hat, and this binding is where it would otherwise get in —
  the response object cannot carry it, so the transport must not either.

  **The rate limiter is inside the exchange, not in front of it.**
  [`core-model.md`](../../spec/core-model.md) §9.1 makes a rate limit required —
  it is what bounds the probing that denials no longer debit for — and
  it is checked at [`core-model.md`](../../spec/core-model.md) §4 step 9a and
  keyed on the requester relationship ([P-008](P-008-capacity-accounting.md)
  §4.7). So it cannot sit at a layer that never saw a Q2D message: that layer
  does not know the principal, because §4.1 keeps it out of the path and the
  headers and inside the signed body.

  A rate-limit rejection is therefore a **Q2D outcome** — HTTP 200, signed body,
  Tier C class, indistinguishable from a policy denial. A transport-layer
  limiter returning 429 would restore at the framing layer exactly the
  distinction the signed body was built to erase, and would do it for the one
  cause whose whole purpose is to close an oracle.
- **No response headers vary with outcome.** Not `Content-Length` beyond what
  the body already determines, not cache directives, not `Vary`. The body's
  uniformity is [P-009](P-009-denial-normalization.md) §4.3's structural
  property; the framing must not undo it.

The payoff is that ordinary web-server access logging becomes safe by default. A
log line records one path, one status, a size, and a timestamp — and size and
timing are already named residual channels in
[`trust-matrix.md`](../../threat-model/trust-matrix.md) §5. Nothing further
leaks because there is nothing further to record.

Access logs must not record the body, and must not be configured to record
request or response headers.

### 4.3 The endpoint set, and the one that was dropped

[`mvp-scope.md`](../mvp-scope.md) §4 listed four endpoints for Stage 6. Three
survived scrutiny, and §4 has been amended to list only those three.

| Endpoint | Purpose | Status |
|---|---|---|
| `POST /.well-known/q2d/query` | The exchange | Keep |
| `GET /.well-known/q2d/capabilities` | Version and suite discovery (§4.4) | Keep, narrowed |
| `GET /.well-known/q2d/pending/{token}` | Explicit-escalation polling (§4.5) | Keep |
| ~~`GET /.well-known/q2d/predicates/{id}/{version}`~~ | Serve a registry entry | **Dropped** — resolved, see below |

The dropped one was two problems.

**It is the existence oracle [P-005](P-005-registry-client.md) §4.7 closes.**
That PRD makes all nine resolution failures produce one wire response, stating
that *a requester must not learn which predicates this custodian supports,
because that is custodian-private policy.* An endpoint that answers
"is this predicate available here?" by returning 200 or 404 is that question
asked directly, with none of the uniformity machinery in the way.

**It makes the entry-digest check vacuous.**
[`core-model.md`](../../spec/core-model.md) §2.4.1 has the requester declare the
digest of the entry *it* built against, so that a divergence between the two
parties' definitions is detected. That works because the two copies are obtained
independently — [`scope.md`](../../spec/scope.md) §4 distributes the manifest
with the application. A requester that fetches the entry from the custodian it
is about to query will always declare a matching digest, and the check that
[P-005](P-005-registry-client.md) §4.5 was rewritten to make fail-closed detects
nothing at all.

**Resolved: dropped.** Registry distribution stays out of band, which is also
[P-005](P-005-registry-client.md) open question 4's resolution. If discovery is
later needed, the shape is authenticated and policy-gated — returning only
entries the requesting principal is already permitted to use — not an open `GET`.
Note that the gated variant fixes only the first problem: a requester permitted
to fetch an entry still declares a digest matching the one it was handed, so the
§2.4.1 check stays vacuous for exactly those entries.

[`mvp-scope.md`](../mvp-scope.md) §4 is amended. One consequence is deliberate
and recorded rather than left to be discovered: the deposited technical report
lists this endpoint, and the deposit is immutable. The divergence is tracked in
[`versioning.md`](../versioning.md) § *Known divergences from the deposited
report*, and `paper/src/manuscript.md` is **not** edited — it is the input the
`make repro` gate rebuilds Draft 0.2.1 from, and changing it would break the
check that makes the deposit verifiable.

### 4.4 Capabilities: what may be advertised, and what must not

The document carries the core protocol version, the assurance profiles
supported, and the signature suites accepted. It carries **no predicate list, no
registry identifier, and no manifest digest.**

Suites are advertised because
[`crypto-suites.md`](../../spec/crypto-suites.md) §4 requires rejection to name
no alternative, which leaves a requester unable to discover an acceptable suite
except by trying them — and trying them is exactly the probe §4 forbids
answering one rejection at a time. Advertising once, deliberately, is what that
section anticipates. This resolves [P-003](P-003-crypto-suites.md) open
question 5.

The advertised set is **configuration, defaulting to the mandatory-to-implement
suite alone.** With one registered suite in 0.1 the disclosure is nil; when a
second exists, advertising it is a real statement about local policy, and the
default must not quietly make that statement on a deployment's behalf.

The manifest digest is absent for [P-005](P-005-registry-client.md) §4.3's
reason: a custodian learning that a new digest exists through a channel is the
beginning of an update channel, and §4.3 forbids one. This resolves
[P-005](P-005-registry-client.md) open question 4 — out of band, and the
capability document is not it.

### 4.5 The pending endpoint

`GET /pending/{token}` exists **only** for explicit escalation. Opaque
escalation returns the normalized denial
([P-009](P-009-denial-normalization.md) §4.6) and issues no token, so there is
nothing to poll and the endpoint is unreachable for it.

Transport-level rules, with the semantics belonging to
[P-015](P-015-escalation-lifecycle.md):

- The token is opaque and high-entropy. It encodes nothing — not the
  `query_id`, not the predicate, not the principal. A token that encodes is a
  token that can be read.
- Unknown, expired, and still-pending tokens return an **identical** response.
  A decided outcome differs, which is the endpoint's entire purpose and is the
  residual oracle [`core-model.md`](../../spec/core-model.md) §5.3 already
  names.
- Status 200 throughout, per §4.2 — including for an unknown token, which must
  not be a 404.

**A poll is not an exchange, and its response has two shapes.** This matters
because the obvious reading — "the poll returns a Q2D response" — cannot be
implemented for an unknown token: there is no originating query, so there is no
`request_digest` to bind and no receipt that would mean anything. Fabricating one
would put a signed attestation to a nonexistent exchange on the wire.

| Token state | Response |
|---|---|
| Unknown, expired, or still pending | A **poll status object**: signed, fixed-length, carrying no receipt and no request digest. **Byte-identical across all three states, signature included** |
| Decided | A **poll outcome object**: signed, stating *approved* or *refused*, bound to the original request digest. Carries no receipt, and **is not an answer** |

**A decided poll does not return the answer, and it does not return the original
exchange's cached response either.** The cached response for that exchange is the
`status: escalate` with its token ([P-004](P-004-replay-idempotency.md) §4.7),
which is what an identical retry returns and is not the outcome the poller is
waiting for.

What an approval produces is a **grant**, not a release. The requester submits a
**fresh signed query**, which is revalidated end to end
([`core-model.md`](../../spec/core-model.md) §5.3,
[P-015](P-015-escalation-lifecycle.md) §4.4) and produces the answer with its own
receipt. The poll only reports that the wait is over.

This keeps the two escalation modes aligned on the property that matters: **no
path exists from an approval to an answer that skips revalidation.** A poll that
returned the answer would be that path, and would also hand a bearer token the
disclosure rather than the news that it may now be requested.

No receipt is constructed for a poll in either state.
[`core-model.md`](../../spec/core-model.md) §6 says why: a poll answers *has the
outcome changed?*, not *what is the answer?*, so it is not a response to a query
and has no exchange to bind.

The poll status object carries no field that varies with token state — no
`expires_at`, no retry hint, no reason, no token echo. Three states, one set of
bytes, **signature included**: Ed25519 is deterministic
([P-003](P-003-crypto-suites.md) §7 asserts byte-identical signatures for the
same key and payload), so identical content under the same key signs to identical
bytes. A differing signature would therefore mean the content
differed, which is the leak this row exists to prevent — so uniformity is asserted
over the whole response and not over the body with the signature exempted.

A consequence worth stating: the object cannot carry a timestamp. One would vary
per response and make every poll distinguishable from every other, which defeats
nothing on its own but removes the property that makes this checkable at all.

### 4.6 The daemon refuses to start rather than start degraded

Every prior PRD placed a fail-closed condition at startup. This is where they
become one list, and the daemon that starts is one that can serve every request
it will accept.

| Refuses to start when | From |
|---|---|
| The manifest is absent, unsigned, signed by an unpinned key, or does not match the pinned digest | [P-005](P-005-registry-client.md) §4.2 |
| Any stored `entry_digest` does not recompute | [P-005](P-005-registry-client.md) §5 |
| A registry entry has no predicate implementation, or an implementation has no entry | [P-010](P-010-responder-pipeline.md) §4.3 |
| No audit retention period is configured | [P-011](P-011-receipts-audit.md) §4.7 |
| The suite policy floor is unset, or configuration lowers the compiled floor | [P-003](P-003-crypto-suites.md) open question 2 |
| No signing key resolves, or the policy engine has no authority configuration | [P-007](P-007-policy-engine.md) |
| The replay cache or budget store cannot be opened | [P-004](P-004-replay-idempotency.md) §4.6 |
| **No rate limit is configured** | [`core-model.md`](../../spec/core-model.md) §9.1 — it is required, with no default, because it is what bounds the probing denials no longer debit for |

A daemon that starts and then cannot serve what it advertises is worse than one
that refuses to start, because the failure surfaces as a denial the requester
cannot distinguish from policy.

**Single instance.** Two daemons behind a load balancer would share a replay
cache and a budget store, and [P-004](P-004-replay-idempotency.md) §4.6 requires
the debit and the cache entry to commit atomically — which across instances is a
distributed-transaction problem MVP does not solve. The daemon serves from one
process, and this resolves [P-004](P-004-replay-idempotency.md) open question 2.

### 4.7 TLS, and what it does not add

TLS 1.3 is required. It is not optional and there is no plaintext mode, in any
build configuration.

**No Q2D claim depends on it.** Q2D-C-05 and Q2D-C-06 rest on signatures over
exact bytes; an attacker who strips TLS can read an exchange but cannot alter
one undetectably. What TLS adds is confidentiality for `routing`, which
[`core-model.md`](../../spec/core-model.md) §2.1 notes travels in the clear at
the Q2D layer, and for the relationship metadata around it.

What it does not add is anything on
[`trust-matrix.md`](../../threat-model/trust-matrix.md) §5's list. Message size,
response timing, connection patterns, and the mere fact of an exchange between
two parties survive TLS, and no document may describe the binding as closing
them.

**No client certificates.** Identity is the pairing profile
(**P-014**), and authenticating a requester at the TLS layer would create a
second identity mechanism with no relationship to the one the signature carries
— a binding deciding something the signature covers, which §4.1 exists to
prevent.

### 4.8 Binding transparency is testable; binding equivalence is not

Q2D-C-11 compares two bindings. One binding cannot demonstrate it, and no
artifact from this stage may suggest otherwise.

What one binding **can** demonstrate is transparency:

> For the same envelope bytes, the response returned through the HTTP surface is
> byte-identical to the response [P-010](P-010-responder-pipeline.md)'s
> `process` returns when called directly.

That is a real property, it is testable today, and it is the half of Q2D-C-11
that belongs to each binding individually — a binding that is transparent
against the core cannot be the reason two bindings later disagree. The corpus
group in §6 builds the instrument; a second binding is what would let it be
pointed at the claim.

Describe it as **binding transparency**. Not equivalence, and not conformance to
CC-8 or CC-9, which are the MCP and A2A classes and do not apply here.

**This binding now has its own class: CC-12**
([`conformance-classes.md`](../../spec/conformance-classes.md)), whose must and
must-not lists are §4.1–§4.5 restated as conformance requirements. That is what
this stage may state about itself.

CC-12 does **not** let Stage 6 claim Q2D-C-11. A class for one binding supplies a
binding to compare and demonstrates nothing on its own; the claim holds once two
of CC-8, CC-9, and CC-12 pass the same vector set.
[`conformance-classes.md`](../../spec/conformance-classes.md)'s coverage table
says so directly, so the distinction survives being read out of context.
[`mvp-scope.md`](../mvp-scope.md) §4 Stage 6 is amended accordingly: **claims
none, conformance CC-12**, in two separate fields.

### 4.9 Partial failure

| Interrupted after | State | Resolution |
|---|---|---|
| Body received, connection dropped before `process` | No exchange | Nothing recorded; the request never authenticated |
| `process` returned, connection dropped before the response was written | Debit and cache committed | The requester retries identical bytes and receives the cached response verbatim ([P-004](P-004-replay-idempotency.md) §4.5) |
| Response partially written | Same | Same — the transport never re-invokes `process` |
| Shutdown signal received mid-exchange | In flight | Finish in-flight exchanges, refuse new ones, then exit. A killed exchange is row 2 |

Row 2 is why [P-004](P-004-replay-idempotency.md) caches response bytes rather
than decisions, and why [P-012](P-012-requester-runtime.md) §4.6 never reissues:
the two halves of the retry contract meet at this row, and both must hold for it
to be safe.

## 5. Interfaces

The wire surface is the interface. Both implementations serve the same one.

```
POST /.well-known/q2d/query
    Content-Type: application/q2d+json
    body:  { "signed": "<JWS compact>", "routing": { … } }
    200:   signed response body, any outcome
    4xx:   transport failure only; no signed body

GET  /.well-known/q2d/capabilities
    200:   { q2d_version, assurance_profiles, signature_suites }

GET  /.well-known/q2d/pending/{token}
    200:   signed response body
```

Internal, and deliberately thin:

```
serve(config: DaemonConfig) -> Result            // validates §4.6, then listens
handle_query(body: bytes) -> HttpResponse        // calls process; adds no decision
handle_capabilities(config) -> HttpResponse      // reads configuration only
load_config(path) -> Result<DaemonConfig>        // no message-derived input
```

`handle_query` returning an `HttpResponse` built from `process`'s output and
**nothing else** is the module's central constraint. It has no access to the
`Decision`, the `InternalReason`, or the step recorder — the same shape as
[P-009](P-009-denial-normalization.md) §4.5's `build_denial`, applied one layer
out.

Transport size limits are [P-002](P-002-message-envelope.md) §4.8's envelope
limit enforced at the socket, before the body is buffered.

## 6. Corpus sections

`binding/` — authored under this PRD. Vectors describe an HTTP exchange rather
than a structure, which is a new vector shape; see open question 5.

| Group | Vectors |
|---|---|
| `binding/transparency/` | Response through HTTP byte-identical to `process` directly, for answer, deny, and escalate |
| `binding/status/` | All three outcomes return identical status and headers; transport failures return 4xx with no signed body |
| `binding/headers/` | A header carrying a Q2D field is ignored and does not alter the outcome |
| `binding/limits/` | Oversized body rejected at the socket; wrong content type; unknown path |
| `binding/idempotent/` | Identical body returns identical bytes; no transport-level idempotency key is honoured |
| `binding/capabilities/` | Advertised set matches configuration; no predicate list, registry identifier, or manifest digest |
| `binding/pending/` | Unknown, expired, and pending tokens indistinguishable; decided outcome differs |
| `binding/startup/` | Each §4.6 row refuses to start |

## 7. Acceptance

- [ ] Both implementations serve byte-identical responses through the binding
      for every `binding/transparency/` vector, and each is byte-identical to
      the same envelope through `process`.
- [ ] Every Q2D outcome returns the same HTTP status and the same header set, in
      both implementations.
- [ ] No response to any Q2D outcome carries `Retry-After`, `429`, or `503`.
- [ ] A Q2D field in a header changes no outcome, in any vector.
- [ ] The capability document contains no predicate list, registry identifier,
      or manifest digest, and its suite set comes from configuration.
- [ ] Every §4.6 condition refuses startup, observably, in both implementations.
- [ ] There is no configuration, environment variable, or build feature that
      serves without TLS.
- [ ] The Rust requester completes an exchange against the Go daemon and the
      reverse — [`mvp-scope.md`](../mvp-scope.md) §1 item 7. **Not `harness
      cross`**, which runs two runners over a corpus of static vectors and
      speaks no transport; a live exchange between two processes is this PRD's
      own interop check and needs a harness that does not exist yet. Naming a
      mode that cannot do it would leave the criterion looking covered. Owned
      here; see [P-001](P-001-conformance-corpus.md) §3 for why the conformance
      harness is not the place for it.
- [ ] The [`mvp-scope.md`](../mvp-scope.md) §1 walkthrough completes on two
      machines by someone following the quickstart and nothing else.

The last item is the stage gate and cannot be self-certified. It needs someone
who did not write the quickstart.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| A status code distinguishing an answer from a denial | `binding/status/` comparison across outcomes |
| A status code distinguishing two denials | Same, and it defeats Q2D-C-08 one layer above where it was established |
| `Retry-After`, `429`, or `503` on a Q2D outcome | Present at all — it is retry metadata under another name |
| A response header varying with outcome | Header-set comparison across `binding/status/` |
| A Q2D field read from a header, path, or query parameter | `binding/headers/` vector alters an outcome |
| A predicate, principal, or query identifier in a URL path | Present; it reaches every intermediary's log |
| The capability document listing predicates | `binding/capabilities/`; it is [P-005](P-005-registry-client.md) §4.7's oracle restored |
| A transport-level idempotency key honoured | Two distinct exchanges collapse, or one splits |
| Access logging configured to record bodies or headers | Configuration review; the default must be safe |
| A daemon starting with any §4.6 condition unmet | `binding/startup/` vector starts |
| Serving without TLS in any configuration | Grep for a bypass finds one |
| TLS client certificates authenticating a requester | A second identity mechanism exists |
| Text describing the binding as demonstrating Q2D-C-11, or as CC-8/CC-9 conformant | Grep across quickstart, README, and comments |
| A second timing-padding mechanism in the transport | Present; [P-009](P-009-denial-normalization.md) §4.7 owns the only one |

Rows 1 and 2 are the ones this PRD exists for. Three PRDs made denials
indistinguishable in the body, and a single `403` in a handler would undo all of
it in a way no body-level test would catch.

Row 13 is the claim-honesty surface. A quickstart is marketing whether or not it
is written as such, and it is the artifact an outsider reads first.

## 9. Escalate-if-changed decisions

1. **The body is the envelope. No Q2D field appears in a header, path, or query
   parameter**, and none is read from one.
2. **One HTTP status for every signed response.** 4xx is reserved for requests
   that never became an exchange.
3. **No retry metadata at the transport layer**, in any form, including status
   codes that imply it.
4. **No response header varies with outcome.**
5. **The capability document advertises version, profiles, and suites — never
   predicates, the registry identifier, or the manifest digest.**
6. **The advertised suite set is configuration, defaulting to the MTI alone.**
7. **The daemon refuses to start on any §4.6 condition**, rather than degrading.
8. **Single instance**, because atomic debit-and-cache does not survive
   horizontal scaling without a distributed transaction.
9. **TLS 1.3 required, with no bypass and no client-certificate identity.**
10. **The binding adds no timing mechanism of its own.**

## 10. Open questions

| Question | Belongs to |
|---|---|
| **1.** ~~`GET /predicates/{id}/{version}` (§4.3) is an existence oracle and makes the §2.4.1 entry-digest check vacuous~~ | **Resolved: dropped.** [`mvp-scope.md`](../mvp-scope.md) §4 amended; §4.3 rewritten. The deposited report still lists it — divergence recorded in [`versioning.md`](../versioning.md), and `paper/src/manuscript.md` deliberately left alone so `make repro` keeps working |
| **2.** ~~No conformance class covers a direct HTTPS binding~~ | **Resolved: CC-12 added**, with §4.1–4.5 as its must and must-not lists, and added to Q2D-C-11's owning classes with an explicit note that one class does not establish the claim. [P-014](P-014-identity-pairing.md) open question 2 was decided the other way, and the reason is written down in both PRDs: a class can be written for a boundary that is settled, and this one is — P-014's is the open question |
| **2a.** ~~[`mvp-scope.md`](../mvp-scope.md) §4 lists "Claims: Q2D-C-11" for Stage 6~~ | **Resolved.** Stage 6 claims **none**, and states **conformance: CC-12** in a separate field. A parenthetical qualifier does not survive transcription into a coverage table; an empty claims cell with a stated reason does |
| **3.** ~~Should capability discovery advertise suites?~~ | **Answered:** yes, from configuration, defaulting to the MTI alone. §4.4. Resolves [P-003](P-003-crypto-suites.md) open question 5 |
| **4.** ~~How does a custodian learn a new manifest digest exists?~~ | **Answered:** out of band; the capability document does not carry it. §4.4. Resolves [P-005](P-005-registry-client.md) open question 4 |
| **5.** ~~The corpus has no vector shape for an HTTP exchange~~ | **Resolved: one new operation, `http_exchange`** — input is a method, path, headers, and body; output is status, headers, and body. The harness still never speaks Q2D: it moves opaque bytes and compares them. Named in [P-001](P-001-conformance-corpus.md) §4.5 and settled under its issue 17 with the rest of the Stage 5–8 vocabulary, so this PRD does not name it unilaterally |
| **6.** ~~`.well-known/q2d` is not an IANA-registered well-known URI (RFC 8615 §3)~~ | **Resolved: the base path is configuration, defaulting to `/.well-known/q2d`.** Registration is tracked separately and is not an MVP deliverable. **No artifact may describe the path as registered, allocated, or reserved** — it is a default, and saying otherwise would be a claim about an IANA registry this project has not entered. Configurability is also what lets a deployment avoid a collision if the name is ever taken by someone else |
| **7.** ~~Does polling `/pending/{token}` require an authenticated request?~~ | **Answered:** a bearer token in MVP, named as a weakening; a signed poll needs a core message type. [P-015](P-015-escalation-lifecycle.md) §4.2. The weakness is now recorded in [`trust-matrix.md`](../../threat-model/trust-matrix.md) §5 rather than only in a PRD |
| **8.** ~~Does the daemon need a health endpoint, and what may it reveal?~~ | **Resolved: yes — a separate listener bound to loopback, returning liveness only.** Not on the public listener, and not carrying registry state, policy state, predicate names, budget state, or counts. A health endpoint reporting which predicates loaded is the existence oracle §4.3 just removed, rebuilt on a different port; one reporting budget or denial counts leaks other requesters' activity, which [P-011](P-011-receipts-audit.md) §4.3 keeps out of receipts for the same reason. Liveness is a boolean and needs no detail to be useful |

Questions 3 and 4 arrived from other PRDs and are closed here. Questions 1 and 2
are the ones this PRD found, and both change documents above it.

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | ~~Escalate open questions 1 and 2~~ — **done** | Resolved; endpoint dropped, CC-12 added; §4.3 and §4.8 cite the outcome |
| 1a | CC-12 conformance suite: a positive and a negative test for every must and must-not | `binding/` groups cover each; no must is asserted only by review |
| 2 | `DaemonConfig` and `load_config` | No constructor accepts message-derived input |
| 3 | Startup validation for every §4.6 row | `binding/startup/` passes; each row observable |
| 4 | TLS 1.3 listener, no plaintext path | No bypass reachable from configuration, environment, or build features |
| 5 | `POST /query` handler over `process` | `binding/transparency/` byte-matches the direct call |
| 6 | Status and header policy | `binding/status/` and `binding/headers/` pass; header set constant across outcomes, **including for a rate-limit rejection**, which returns 200 with a signed Tier C body and never a 429 |
| 7 | Socket-level size limits | Oversized body rejected before buffering |
| 8 | `GET /capabilities` from configuration | `binding/capabilities/` passes; no predicate list |
| 9 | `GET /pending/{token}` transport shape | `binding/pending/` passes; open question 5 resolved first |
| 10 | Access-logging policy and safe defaults | No body or header content recorded by default |
| 11 | Graceful shutdown | In-flight exchanges complete; new ones refused |
| 12 | Author `binding/` corpus section | Eight groups; `harness lint` clean |
| 13 | Quickstart, configuration reference, and operational-security notes | An outsider completes [`mvp-scope.md`](../mvp-scope.md) §1 from them alone |
| 14 | Two-machine walkthrough, executed by someone who did not write it | The Stage 6 gate |
| 15 | Claim-language audit across quickstart and operator docs | No text claims Q2D-C-11, CC-8, or CC-9, describes CC-12 as establishing Q2D-C-11, or says TLS closes a residual channel |

Issue 9 blocks
on [P-001](P-001-conformance-corpus.md)'s operation vocabulary, which is the
first time a later stage has needed to extend it; [P-001](P-001-conformance-corpus.md)
§4.5 anticipated that and requires extension rather than redefinition.
