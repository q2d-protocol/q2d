# Q2D documentation

Implementation- and operator-facing documentation. Distinct from two neighbouring
directories:

- `spec/` — normative protocol definitions (`MUST` / `SHOULD` / `MAY`).
- `paper/` — the technical report and its source package.

Planned contents, per the artifact split in the technical report (§ *Open-source
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
