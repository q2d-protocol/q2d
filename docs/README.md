# Q2D documentation

Implementation- and operator-facing documentation. Distinct from two neighbouring
directories:

- `spec/` — normative protocol definitions (`MUST` / `SHOULD` / `MAY`).
- `paper/` — the technical report and its source package.

Present:

| File | Purpose |
|---|---|
| [`mvp-scope.md`](mvp-scope.md) | Phase 1 scope, stage order, PRD set, and gates. Parent of the PRD set. |
| [`versioning.md`](versioning.md) | Tag scheme, independent version lines, and the known divergences between the deposited report and the current specification. |
| [`open-escalations.md`](open-escalations.md) | Every escalation, open or closed, with the options considered and a **Cascade** line naming each document the decision touches. |
| [`prds/`](prds/) | The sixteen PRDs and their registry. |

Planned, per the artifact split in the technical report (§ *Open-source
and governance posture*):

| File | Purpose |
|---|---|
| `quickstart.md` | Run a requester and a custodian locally; one predicate end to end. |
| `deployment.md` | Custodian daemon, key management, registry pinning, relay. |
| `privacy-properties.md` | What each deployment profile does and does not achieve, in operator language. |
| `operational-security.md` | Key rotation, revocation, audit-store handling, incident response. |
| `gdpr-control-mapping.md` | Article-by-article technical support and gaps. Requires review by qualified counsel before any public compliance claim. |

Nothing here is normative. Where this documentation and `spec/` disagree, `spec/`
governs.
