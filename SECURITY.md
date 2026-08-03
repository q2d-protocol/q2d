# Security Policy

## What this project currently is

Q2D is a **pre-release protocol specification**. There is no reference
implementation, no conformance suite, and no deployed system. The published
artifact is a technical report and a specification spine.

That shapes what a security report means here. The most valuable findings are
not memory-safety bugs or injection flaws — there is no code to have them. They
are **defects in the design**: a claim that does not hold, an attack the threat
model misses, or a gap between what a mechanism does and what the specification
says it achieves.

This policy will be revised when the reference implementation exists.

## What we consider a security issue

**In scope, and most wanted:**

- A claim in [`spec/claims.md`](spec/claims.md) that **does not hold under its own
  stated assumptions**. Each claim names what it requires and how it fails; a
  case where it fails while its assumptions hold is a defect.
- An attack absent from [`threat-model/trust-matrix.md`](threat-model/trust-matrix.md),
  or a trusted-component row that is understated.
- An ordering or state flaw in [`spec/core-model.md`](spec/core-model.md) §4 —
  particularly anything reaching private input before step 16, or any way to
  learn *which* validation step rejected a request where denial normalization
  is required.
- A way for a requester to influence the effective answer domain, the capacity
  debit, or the assurance profile actually used.
- A residual channel not named in the threat model's §5.
- A cryptographic issue in [`spec/crypto-suites.md`](spec/crypto-suites.md) —
  suite substitution, downgrade, or signature binding.
- Anywhere the specification's language overstates what a mechanism delivers.
  Claim-language defects are security defects here: an implementer who believes
  a stronger claim deploys accordingly.

**Out of scope:**

- Vulnerabilities in the technical report's build tooling (`paper/`), unless
  they affect a published artifact's integrity.
- The project website, beyond content accuracy.
- Anything requiring a compromised computation executor. That is
  [`Q2D-NC-06`](spec/claims.md) — a stated non-claim, not a finding.
- Reports that a non-claim is not achieved. The claims document is explicit
  about what Q2D does not do; that list is the answer, not the bug.

If you are unsure whether something qualifies, report it. A misrouted report
costs us a few minutes; an unreported design flaw costs implementers far more.

## How to report

**Use GitHub private vulnerability reporting:**
[github.com/q2d-protocol/q2d/security/advisories/new](https://github.com/q2d-protocol/q2d/security/advisories/new)

This keeps the report private until we agree it is ready to publish, and needs
no key exchange or mail infrastructure.

Please include: what the issue is, which claim or section it affects, the
assumptions under which it holds, and — if you have one — a concrete sequence
showing the failure. For a specification defect, a worked example of a request
and response that produces the wrong outcome is worth more than a description.

**Do not open a public issue for a security report.** Ordinary specification
questions, ambiguities, and editorial corrections belong in public issues; those
are not security reports and are very welcome there.

## What happens next

| When | What |
|---|---|
| Within 5 business days | Acknowledgement that the report was received. |
| Within 30 days | An assessment: whether we agree it is a defect, and what we intend to do. |
| Up to 90 days | Coordinated disclosure window from the acknowledgement date. |

We will publish sooner if a fix lands sooner, and we will discuss an extension
with you if a finding needs one. If we cannot reach you, we will not publish
until the 90 days have elapsed.

**A defect that invalidates a published claim is disclosed even if it is not
fixed.** A specification whose claims are known to be wrong is more dangerous
than one with an open gap, because implementers rely on claims. We will amend
[`spec/claims.md`](spec/claims.md) and note the change in the next report draft
rather than wait for a mechanism.

## Credit

We will credit you by name and affiliation in the fix commit, the revised
specification, and the next report draft, unless you ask us not to. Tell us how
you would like to be named.

**There is no bug bounty.** This is an unfunded open-source protocol project with
no company behind it. We can offer credit and a genuine response, and nothing
else. Please do not spend effort here expecting payment.

## Safe harbour

We will not pursue or support legal action against anyone who reports a security
issue in good faith under this policy, provided you do not access, modify, or
exfiltrate data that is not yours, do not degrade a service others rely on, and
give us the disclosure window above.

There is no deployed Q2D system to test against, so there should be no occasion
to touch anyone's data. If a future deployment carries the Q2D name, it is
covered by its operator's policy, not this one.

## Publication integrity

The technical report is deposited with a DOI
([10.5281/zenodo.21777305](https://doi.org/10.5281/zenodo.21777305), all
versions). Each release package carries `SHA256SUMS.txt` generated after
assembly. If a published artifact's checksums do not verify, that is a security
report — send it via the link above.
