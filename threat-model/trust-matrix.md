# Q2D Trust Matrix — version 0.1

**Protocol version:** 0.1 (pre-release)
**Document status:** Threat-model spine — working draft.

What must be trusted for each Q2D claim to hold, and what happens when each
trusted component is compromised.

A claim without a named trusted computing base is not a security claim. This
document supplies that base for every claim in [`../spec/claims.md`](../spec/claims.md).

Terms: [`../spec/terminology.md`](../spec/terminology.md).
Exchange: [`../spec/core-model.md`](../spec/core-model.md).

---

## 1. Trust vocabulary

| Level | Means |
|---|---|
| **Trusted** | The property fails if this component misbehaves. No mechanism detects it. |
| **Verified** | Trusted only after a check the protocol defines. Compromise before the check is caught; compromise of the checking mechanism is not. |
| **Untrusted** | Assumed hostile. No property depends on its good behaviour. |
| **N/A** | Not involved in this property. |

"Trusted" is a statement about the design, not an endorsement. Every trusted
component is an attack target and appears in §4.

---

## 2. The matrix

Rows are components. Columns are the source-side claims that hold at the
`authenticated-answer` profile, plus the two conditional requester-side claims.

| Component | C-02 domain | C-03 bounded | C-04 confinement | C-06 auth | C-07 replay | C-09 budget | C-13 flow |
|---|---|---|---|---|---|---|---|
| Requester agent (LLM) | Untrusted | Untrusted | Untrusted | Untrusted | Untrusted | Untrusted | Untrusted |
| Requester runtime | Untrusted | Untrusted | Untrusted | Verified | Untrusted | Untrusted | **Trusted** |
| Network / relay | Untrusted | Untrusted | Untrusted | Untrusted | Untrusted | Untrusted | Untrusted |
| Custodian runtime | Trusted | Trusted | Trusted | Trusted | **Trusted** | **Trusted** | N/A |
| Computation executor | Trusted | **Trusted** | **Trusted** | **Trusted** | Trusted | Trusted | N/A |
| Policy engine | Trusted | Trusted | Trusted | N/A | N/A | **Trusted** | N/A |
| Predicate registry | **Trusted** | Trusted | Trusted | N/A | N/A | Trusted | N/A |
| Predicate implementation | Trusted | **Trusted** | **Trusted** | N/A | N/A | Trusted | N/A |
| Identity / key infrastructure | Verified | N/A | N/A | **Trusted** | Trusted | Trusted | N/A |
| Protected data source | N/A | N/A | Trusted | N/A | N/A | N/A | N/A |
| Model provider endpoint | N/A | N/A | N/A | N/A | N/A | N/A | **Untrusted sink** |
| Logs, traces, memory | N/A | N/A | N/A | N/A | N/A | N/A | **Untrusted sink** |
| External sinks | N/A | N/A | N/A | N/A | N/A | N/A | Untrusted |

**Bold** marks the component whose compromise most directly defeats that claim.

Three readings worth stating explicitly:

- **The requester's LLM is untrusted in every column.** No Q2D property depends
  on model behaviour. That is the point of the design.
- **The requester runtime is trusted for exactly one claim** — C-13 — and
  untrusted everywhere else. Source-side properties survive a fully compromised
  requester.
- **C-13's entire trusted base is requester-side.** A custodian cannot deliver
  it and must not be described as doing so.

## 3. Per-claim trusted computing base

| Claim | Fails if these misbehave |
|---|---|
| **C-01** pre-evaluation commitment | Requester runtime (signs its own contract); canonicalization |
| **C-02** responder-owned domain validation | Registry signing key; registry entry correctness; custodian runtime |
| **C-03** bounded output | Computation executor; predicate implementation; output validator |
| **C-04** source confinement | Computation executor; predicate implementation; error paths |
| **C-05** request binding | Canonicalization; requester key custody |
| **C-06** response authentication | Executor key custody; key-to-principal binding |
| **C-07** replay resistance | Replay cache; clock; executor key custody |
| **C-08** denial normalization | Custodian runtime; policy engine; **plus every timing and state channel outside the protocol** |
| **C-09** capacity accounting | Policy engine; budget store; relationship-establishment cost |
| **C-10** exchange-bound accountability | Custodian runtime; receipt construction; audit store |
| **C-11** binding equivalence | Each binding implementation |
| **C-12** evidence segregation | Requester runtime; the agent framework's result handling |
| **C-13** flow confinement | Requester runtime; **completeness of the sink inventory** |

## 4. Adversaries

| Adversary | Defeats | Does not defeat |
|---|---|---|
| Malicious requester principal | Purpose honesty (never claimed) | Domain validation, bounded output, source confinement |
| Prompt-injected requester agent | Nothing on the source side | C-02 … C-10 |
| Compromised requester runtime | C-12, C-13 entirely | Source-side claims |
| Lying requester (purpose, sinks) | Purpose and sink obligations | Bounded output; the receipt still records the declaration |
| Untrusted network or relay | Nothing, given signatures and payload protection | C-05, C-06 |
| Malicious data item (injection in source content) | Possibly the predicate implementation or a custodian-side model | Bounded output, if the domain check holds |
| Colluding requesters / sinks | C-09 accounting | Per-exchange claims |
| **Compromised computation executor** | **C-03, C-04, C-06 — everything Phase 1 rests on** | Nothing recovers this in 0.1 |
| Compromised registry signing key | C-02, and therefore C-03 and C-09 | C-05, C-06 |
| Compromised policy engine | C-08, C-09 | C-03, C-04 |
| Compromised requester or executor key | C-05 or C-06 respectively, until revocation | Claims not resting on that key |
| Curious model provider / observability platform | C-13 for that path | Source-side claims |
| Repeated-query adversary | Reconstructs beyond what C-09 throttles | Per-exchange bounded output |

Two entries deserve emphasis.

**The computation executor is the single point of failure in Phase 1.** It holds
legitimate plaintext access. Q2D-NC-06 states this as a standing non-claim
rather than a caveat, because no Phase 1 mechanism reduces it. Verifiable
computation and attested-use profiles exist precisely to move this row.

**The registry is the second.** A compromised registry signing key lets an
attacker define what "bounded" means. Phase 1 mitigates by pinning a digest
locally and failing closed on anything unpinned — which converts registry
compromise into an availability problem rather than a disclosure one, provided
the custodian never auto-accepts a new digest.

## 5. Residual channels

Not closed by any 0.1 mechanism. Named so that no claim is read as covering them.

- Message size and response timing
- Queue delay and rate-limit behaviour
- Predicate availability and relationship existence
- Escalation notifications reaching a human
- Budget-exhaustion state transitions
- The opaque-escalation unavailable-to-answer transition
  ([`../spec/core-model.md`](../spec/core-model.md) §5.3)
- Source-freshness observability
- Identity and network metadata; receipt correlation
- Implementation fingerprints

C-08 reduces explicit oracles in the response payload. It does not address this
list. Deployments needing more require padding and scheduling profiles that 0.1
does not define.

## 6. What future profiles move

| Profile | Moves | Introduces |
|---|---|---|
| **Credential-backed** | Input provenance from self-assertion to issuer attestation | Trust in the issuer; the credential's own status infrastructure |
| **Verifiable computation** | Correct execution from trusted to verified — the executor row weakens | Program registry, input-commitment process, proof system |
| **Attested-use** | Which code sees plaintext, from trusted to attested | Hardware vendor, attestation service, build reproducibility, side-channel resistance |
| **Contained runtime** | Downstream flow from unconstrained to mediated | Trust in sink-inventory completeness |

No profile removes trust; each **relocates** it and adds new components. A
profile that appears to eliminate a trusted component has usually moved it
somewhere less visible.

## 7. Maintenance

Adding a claim to [`../spec/claims.md`](../spec/claims.md) requires a row in §3
and a review of §2. A claim whose trusted computing base is not stated here is
incomplete, and the conformance suite should treat it as unverifiable.
