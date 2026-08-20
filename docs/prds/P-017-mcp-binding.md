# P-017 — MCP binding

| Field | Detail |
|---|---|
| PRD | P-017 |
| Stage | 5 — closes the demonstration |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-005](P-005-registry-client.md), [P-009](P-009-denial-normalization.md), [P-010](P-010-responder-pipeline.md), [P-011](P-011-receipts-audit.md) |
| Blocks | P-016 |
| Replaces | [P-013](P-013-https-binding.md) — deferred 2026-08-19 |

---

## 1. Purpose

Serve Q2D over the Model Context Protocol: a library that turns a pinned
predicate manifest into an MCP server whose tools **cannot return out-of-domain
values** and whose answers carry receipts.

This is the artifact the project exists to produce. Everything before it is a
library; this is what somebody imports, points at a manifest, and runs.

**It replaces [P-013](P-013-https-binding.md)'s bespoke HTTPS daemon.** MCP's
`2026-07-28` revision moved further toward ordinary stateless HTTP with
OAuth/CIMD authorization, and re-solving transport worse is not a contribution.
The audience that would run a Q2D custodian already speaks MCP.

**Claims served:** Q2D-C-03 (bounded output) at the surface an agent actually
touches, and Q2D-C-10 (exchange-bound accountability) by returning the receipt
where a caller can read it. **Not Q2D-C-11** — binding equivalence is a statement
*between* bindings, and there is one.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`core-model.md`](../../spec/core-model.md) §4 | The processing order the binding invokes and does not reorder |
| [`core-model.md`](../../spec/core-model.md) §4 step 17 | Output validated against the effective domain — the property this binding exposes as `outputSchema` |
| [`core-model.md`](../../spec/core-model.md) §5.1–§5.3 | The response shapes carried in `structuredContent` |
| [`core-model.md`](../../spec/core-model.md) §5.2.1 | The `external_reason` vocabulary a refusal maps from |
| [`core-model.md`](../../spec/core-model.md) §7 | Idempotency by signed `query_id` and `nonce` — never by a transport key |
| [`core-model.md`](../../spec/core-model.md) §2.8 | Size limits, enforced in the message layer regardless of binding |
| [`scope.md`](../../spec/scope.md) §6 | What makes a binding non-conformant: dropping a field the transport has no place for |
| [`claims.md`](../../spec/claims.md) Q2D-C-03 | Bounded output |
| [`claims.md`](../../spec/claims.md) Q2D-C-10 | Receipt binding |

## 3. Module boundary

**Inside:** the mapping from a registry entry to an MCP tool definition; carriage
of the signed answer contract; invocation of `process`; the refusal shape;
server identity and key configuration; startup validation; the `binding/` corpus
section; the quickstart.

**Explicitly outside:** everything the binding invokes. The processing order is
[P-010](P-010-responder-pipeline.md)'s, the registry is
[P-005](P-005-registry-client.md)'s, receipts are
[P-011](P-011-receipts-audit.md)'s, the refusal *content* is
[P-009](P-009-denial-normalization.md)'s. **This module decides nothing the
signature covers**, and reads no Q2D field from a header, a path, or a tool
argument.

MCP's own transport, authorization, and session semantics are **MCP's**. This
PRD adds no transport of its own and specifies no authorization scheme.

## 4. Design

### 4.1 The answer domain becomes `outputSchema`, and that is the whole idea

| Registry entry | MCP tool |
|---|---|
| Predicate id | `name` |
| Registered question | `description` |
| Input schema | `inputSchema` |
| **Answer domain** | **`outputSchema`** |

The last row is why this binding is worth building rather than merely
convenient.

> In plain MCP, `outputSchema` is declared by the party that fulfils it. The
> server promises a shape and then produces one. That is documentation.

Here the shape comes from a **registry the custodian pinned**, and
[`core-model.md`](../../spec/core-model.md) §4 step 17 validates the released
value against it before the response is signed. The bound is checkable against a
third artifact rather than trusted because the server said so, and a requester
can confirm from the receipt which entry it came from.

**This is also the injection property at the surface.** An MCP tool that returns
a record returns whatever is in the record, including an injected instruction. A
tool whose `outputSchema` is `{"type": "boolean"}` has nowhere to put one. The
corpus asserts it — see §6 and [P-001](P-001-conformance-corpus.md)'s
`injection/` groups.

**`tools/list` advertises what this deployment serves and nothing about the
manifest it pinned.** Serving a predicate already discloses that it is served;
naming the registry, its digest, or entries the custodian holds but does not
implement would restore [P-005](P-005-registry-client.md) §4.7's existence
oracle in the one place every client reads first.

### 4.2 The contract rides in `_meta`, because `inputSchema` means model-authored

`_meta["dev.q2d/contract"]` carries the signed answer contract.

**The decisive argument is about who writes it.** MCP tools are model-controlled:
the language model reads `inputSchema` and fills in the parameters. Putting the
contract there asks a model to produce a signed commitment to purpose, recipient
and permitted sinks — which it cannot do, must not do, and would produce
something plausible-looking instead.

> Anything in `inputSchema` is model-authored by construction. The contract comes
> from the runtime.

`_meta` is the right home on its own terms as well: MCP `2026-07-28` is stateless
and already carries protocol version, client capabilities and client info there
per request. `io.modelcontextprotocol/*` is reserved for MCP, so a reverse-DNS
namespace is the correct citizen behaviour.

Secondary reasons, neither sufficient alone: a contract in `inputSchema` would
appear in every `tools/list` response and burn context, and it would make a
missing contract a schema error rather than a protocol refusal.

**A missing or stripped contract fails closed.** An intermediary that drops
unknown `_meta` keys therefore makes every request fail — safe, but it means
Q2D-over-MCP cannot traverse arbitrary proxies. That is a documented limitation
rather than one to be discovered, and if it proves common the fallback is a
dedicated HTTP header. **Never a tool argument.**

### 4.3 Transparency, not equivalence

> For the same envelope bytes, what the MCP surface returns is byte-identical to
> what `process` returns when called directly.

Call that **binding transparency**. It is the half of Q2D-C-11 that belongs to
each binding on its own, and it is what makes a later second binding's
disagreement attributable.

**Q2D-C-11 itself is not claimed and is marked *not attempted*** — equivalence is
a statement between two bindings and this project builds one. A document
describing CC-12-style class conformance as establishing Q2D-C-11 is making
exactly the error [P-013](P-013-https-binding.md) §4.8 was written to prevent,
and the error survives the binding being replaced.

The handler is constructed from `process`'s output **and nothing else**: no
access to the `Decision`, the `InternalReason`, or the step recorder. The same
shape as `build_denial`, one layer out.

### 4.4 One refusal shape, and MCP's own guidance cuts against it

MCP has two error mechanisms and the split is load-bearing:

| Mechanism | Used for |
|---|---|
| **Protocol errors** (JSON-RPC) | Requests that never became a Q2D exchange — unknown tool, malformed request |
| **Tool execution errors** (`isError: true`) | **Every Q2D refusal** |

Every refusal takes **one shape, with no cause-specific text, no retry guidance,
and no field that varies with cause**. This is where
[P-013](P-013-https-binding.md)'s status-and-header discipline lands: that PRD
forbade a `403` or a `429` because one distinguishing status would undo three
PRDs of body-level uniformity, and **the same trap exists here in a more
tempting form.**

> MCP specifies that tool execution errors should carry *"actionable feedback
> that language models can use to self-correct."* For a Q2D refusal that is
> precisely what must not happen. A helpful *"rate limited, retry in 40 seconds"*
> is the oracle the quota was introduced to close, written by a convention that
> is right about every other tool.

**The divergence is deliberate and documented**, not an oversight to be tidied by
someone following the MCP style guide.

### 4.5 Idempotency is the signed identifier, never a transport key

[`core-model.md`](../../spec/core-model.md) §7 identifies an exchange by signed
`query_id` and `nonce`. A transport-level idempotency key would be a **second,
unsigned** identifier for one exchange, and two identities is how a retry becomes
a distinct request — a second debit, and an outcome that can differ from the
first.

**MCP makes this trap easier to fall into**, which is why it gets its own
section: `2026-07-28`'s multi-round-trip pattern *requires* a different JSON-RPC
request id on a retry, so the transport actively encourages treating each
attempt as new. The binding must not.

## 5. Interfaces

```
serve(manifest: Manifest, config: BindingConfig) -> Server
tool_definitions(manifest) -> [ToolDefinition]      // §4.1's mapping
handle_call(name, arguments, meta) -> ToolResult    // over process()
```

`serve` takes a **verified** `Manifest` — [P-005](P-005-registry-client.md)'s
type, which exists only if it parsed, its signature verified, its digest matched
the pin, and every entry digest recomputed. **There is no constructor that takes
a manifest path**, so a server that started is one whose registry is trusted.

`handle_call` receives `meta` separately from `arguments`, and the two are never
merged. That separation is §4.2's rule in the signature.

## 6. Corpus sections

`binding/` — authored under this PRD, using `http_exchange`, which
[P-001](P-001-conformance-corpus.md) §4.5's settled vocabulary already carries.
**This PRD names no operation of its own.**

| Group | Vectors |
|---|---|
| `binding/transparency/` | The MCP result byte-matches the direct `process` call, for an answer and for a refusal |
| `binding/tools/` | A manifest produces the expected `tools/list`; the answer domain is the `outputSchema`; no registry identifier or digest appears |
| `binding/contract/` | Contract in `_meta` verifies; **absent contract fails closed**; contract in a tool argument is ignored rather than honoured |
| `binding/errors/` | Every refusal cause returns one shape; a quota rejection is byte-identical to a policy denial; no retry metadata |
| `binding/idempotent/` | A retry with the same signed identifiers returns the stored response; a differing JSON-RPC id changes nothing |
| `binding/startup/` | Each §4.6 row refuses to start, observably |

The `injection/` groups are [P-001](P-001-conformance-corpus.md)'s rather than
this PRD's, because they are properties of the protocol and not of the binding —
but `binding/tools/` is where the `outputSchema` half of them becomes visible to
a client.

### 4.6 Startup validation

| Refuses to start when | From |
|---|---|
| Manifest absent, unsigned, unpinned key, or digest mismatch | [P-005](P-005-registry-client.md) §4.2 |
| Any stored `entry_digest` does not recompute | [P-005](P-005-registry-client.md) §5 |
| A registry entry has no implementation, or an implementation no entry | [P-010](P-010-responder-pipeline.md) §4.3 |
| Suite policy floor unset, or configuration lowers the compiled floor | [P-003](P-003-crypto-suites.md) |
| No signing key resolves, or the policy engine has no authority configuration | [P-007](P-007-policy-engine.md) |
| The replay cache cannot be opened | [P-004](P-004-replay-idempotency.md) §4.6 |
| **No request quota configured** | [`core-model.md`](../../spec/core-model.md) §9.1 |
| Key file permissions loose | §4.7 |

> A server that starts and then cannot serve what it advertises is worse than one
> that refuses to start, because the failure reaches the requester as a refusal
> it cannot distinguish from policy.

**Single instance.** Two servers would share a replay cache, and MCP's removal of
protocol-level sessions does not change that: the cache is Q2D state, not
transport state.

### 4.7 Identity is a configured key list

Not a pairing profile. [P-014](P-014-identity-pairing.md) is deferred, and this
binding resolves requester keys from a list an operator entered, exactly as
`SuitePolicy` and `RegistryPins` are configured: no constructor accepts
message-derived input, no fetch, no discovery, no fallback.
[P-003](P-003-crypto-suites.md)'s `resolve_key` interface is already built and
this supplies the deployment's implementation of it.

**Delegation is a no-op** under this profile, and the quickstart says so rather
than letting a reader assume [`core-model.md`](../../spec/core-model.md) §4 step
7 ran.

Key material is file-based with permission enforcement — no passphrase, because a
server that cannot start unattended is one an operator will work around by
storing the passphrase beside the key. **The trade is stated: key confidentiality
rests on filesystem permissions.**

## 7. Acceptance

- [ ] For the same envelope bytes, the MCP result byte-matches `process` — both
      implementations, `binding/transparency/`.
- [ ] A manifest's answer domain appears as the tool's `outputSchema`, and a
      value outside it never leaves the server.
- [ ] A signed contract in `_meta` is honoured; **an absent one fails closed**.
- [ ] Every refusal cause produces one shape, asserted **across causes**.
- [ ] A retry with the same signed identifiers returns the stored response, under
      a different JSON-RPC request id.
- [ ] Each §4.6 row refuses to start.
- [ ] Someone who did not write it stands up a server from the quickstart alone.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| A contract supplied as a tool argument | Ignored; the request fails closed as though none was supplied |
| A refusal carrying a cause | A `binding/errors/` vector comparing two causes finds differing bytes |
| Retry guidance in a tool error | Same |
| A transport idempotency key honoured | Two requests with one signed `query_id` and differing transport ids produce two debits |
| `tools/list` naming the registry or its digest | A `binding/tools/` vector finds the field |
| An out-of-domain value reaching `structuredContent` | Step 17 did not run, or ran after serialization |
| A tool defined for a predicate with no implementation | Startup succeeded when §4.6 row 3 says it must not |

## 9. Escalate-if-changed decisions

1. **The contract rides in `_meta`, never in `inputSchema`.** Anything in the
   input schema is model-authored.
2. **`outputSchema` comes from the pinned registry entry**, not from the server's
   own declaration. This is the PRD's reason to exist.
3. **One refusal shape**, against MCP's stated convention for tool errors.
4. **Idempotency is the signed identifier.** No transport key, ever.
5. **`tools/list` discloses no registry state.**
6. **This binding claims transparency, not equivalence.** Q2D-C-11 needs two.

## 10. Open questions

| Question | Belongs to |
|---|---|
| Does the result also carry serialized JSON in a `TextContent` block, as MCP suggests for backwards compatibility? It puts the answer into a channel a model reads as prose, which is the channel §4.1's bound exists to keep narrow. Leaning: **no**, and say why | This PRD, issue 3 |
| Does the binding expose a Q2D-aware capability advertisement at all, or is `tools/list` the whole surface? [P-013](P-013-https-binding.md) §4.4 advertised suites so a requester could discover an acceptable one without probing; MCP has no natural place for it | This PRD |
| Whether a Python distribution wraps this via bindings or reimplements it — the artifact people import lives in an ecosystem, and the answer changes what this PRD ships | Peter; recorded in the scope-reduction decision 3 |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Registry entry → MCP tool definition | A manifest produces `tools/list`; the answer domain is the `outputSchema`; no registry state disclosed |
| 2 | Contract carriage in `_meta` under `dev.q2d/` | `binding/contract/` passes, **including the absent-contract case failing closed** |
| 3 | `tools/call` → `process` → answer and receipt in `structuredContent` | `binding/transparency/` byte-matches the direct call; open question 1 resolved |
| 4 | Refusals map to one MCP error shape | `binding/errors/` passes **across causes**, not per cause |
| 5 | Server identity and key configuration | Configured key list; delegation documented as a no-op; loose key permissions refuse startup |
| 6 | Config loading and startup validation | Each §4.6 row observable |
| 7 | Author `binding/` corpus section | Six groups; `harness lint` clean |
| 8 | Quickstart: point it at a manifest, get a server | An outsider completes it; the limitations in §4.2, §4.7 and the non-claims are carried rather than glossed |

Issue 1 blocks 3 and 7. Issue 2 is independent and can start immediately.
