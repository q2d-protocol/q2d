# Go conventions

**Scope:** language-specific decisions only. Anything that changes what Q2D
*means* belongs in [`spec/`](spec/); anything that changes how a module is built
and verified belongs in its PRD. If a decision here would make the Rust and Go
implementations behave differently, it is in the wrong document —
[`docs/mvp-scope.md`](docs/mvp-scope.md) §6.

Written at Stage 1, as that section requires, and revised rarely.

---

## 1. The shape of the package

- **One package, `q2d`, at the module root**, with the conformance runner under
  `cmd/q2d-conform/`. Flat because the protocol surface is small and a package
  boundary that exists to be tidy costs an import cycle later.
- **One file per specification concern**, named for the concern: `value.go`,
  `parse.go`, `envelope.go`, `routing.go`, `digest.go`, `base64url.go`,
  `ed25519.go`, `version.go`. Tests sit beside them.
- **Exported names carry the protocol's vocabulary**, not Go's: `ParseEnvelope`,
  `ProjectRouting`, `SerializeOperationData`.
- **Errors:** `errors.New` for a condition a caller compares against —
  `ErrSignatureInvalid` — and `fmt.Errorf` for one it only reports. A caller
  branching on an error is the signal to give it a value.
- **No error carries a private value.** Not the offending byte, not the offset,
  not the key. This is [`core-model.md`](spec/core-model.md) §5.2's rule and it
  reaches every `fmt.Errorf` in the package.

## 2. Dependency policy

**Default: the standard library.** Go's is large enough that most of Q2D needs
nothing else, and the packages that would be most convenient are the ones to
avoid:

- **`encoding/json` is not used**, anywhere. It resolves duplicate keys by
  last-wins, which is the rule [`serialization.md`](spec/serialization.md) §2
  requires *rejecting*; it decodes every number into `float64`, losing an
  `int64` above 2^53 silently; and it substitutes U+FFFD for invalid UTF-8.
  Three of `parse.go`'s four refusals are behaviours it deliberately does not
  have.
- **`encoding/base64` is not used** for signed material. `RawURLEncoding` has
  the right alphabet and the right padding and accepts non-canonical trailing
  bits, which RFC 4648 §3.5 permits and a signature does not.
- **`crypto/sha256` *is* used.** The question is never *standard library or
  not* but *does it do what the specification says* — for SHA-256 it does,
  exactly, and for JSON it does not.

**Today the list is one module beyond the standard library.**

```
filippo.io/edwards25519 v1.1.0
```

It is there for one reason, and the reason is a cross-implementation
disagreement rather than a convenience.

`crypto/ed25519.Verify` implements two of the four rules
[`crypto-suites.md`](spec/crypto-suites.md) §3 states, half of a third, and not
the one that matters most here: it does **not** reject a small-order public key.
With `A = R = the identity point` and `S = 0`, the verification equation reduces
to `identity = identity` and holds for *every* message — a universal forgery
requiring no private key, which `crypto/ed25519` accepts and which
`ed25519-dalek`'s `verify_strict` refuses.

The half it does not implement is the canonical field encoding in rule 1, and
**neither library does** — `edwards25519.Point.SetBytes` and dalek's
`VerifyingKey::from_bytes` accept the same non-canonical encodings. That one is
a byte comparison in `canonicalPoint`, written identically in both languages, so
the rule is one test rather than two libraries' opinions of it.

Rust pins the strict rule ([E-47](docs/open-escalations.md)), so Go has to reach
it too, and reaching it needs point arithmetic the standard library does not
export. `edwards25519` is the standard library's own implementation, published
separately by its author; `crypto/ed25519` is built on the internal copy of it.

The check is **computed, not looked up**: `[8]P` is compared against the
identity, which is exactly what dalek's `is_weak` does. The alternative was a
blacklist of the eight small-order encodings, and it lost because a blacklist
needs its own completeness argument and one that is an entry short fails open.

`ed25519.go`'s header states all four acceptance rules, and
[`testdata/ed25519-acceptance.txt`](testdata/README.md) holds both
implementations to the same answers on the ten cases RFC 8032 does not decide.

**Adding a second dependency is an escalation**, not a commit.

**`go.sum` is committed**, and `go.mod` pins an exact version rather than a
range.

## 3. Testing

- **`go test` and the standard library only.** No assertion framework: a table
  test with `t.Errorf` is legible to a reviewer who does not know the framework,
  and every reviewer here is one.
- **Table-driven where the cases are data**, explicit where each case has its
  own reason. A table of eight cases with eight different explanations is eight
  tests wearing a table.
- **Negative cases are not optional.** For this protocol the interesting
  behaviour is what it refuses.
- **Mirrored tests are the weakest form of agreement.** Two suites written to
  match catch a divergence only where someone thought to write the same case
  twice. Where a rule matters, it goes in `testdata/` or the corpus, and the
  Go test reads the same file the Rust one does.
- **`t.Helper()` in helpers**, so a failure reports the line of the case rather
  than the line of the assertion.

## 4. Idiom

- `gofmt`, no configuration. `go vet` runs in CI and is expected to be silent.
- Comments explain *why*; the signature explains what.
- **Deep-copy on the way out of an accessor that returns a map or slice.**
  `Routing.Value()` copies, because handing back the stored value would let a
  caller write `r.Value().(q2d.Object)["purpose"] = …` — authoring a routing
  field through the API that exists to prevent it. Rust gets this from an
  immutable borrow; Go has to copy, and a test mutates a nested member to prove
  a shallow copy would not do.
- **A `nil` value of an interface type is a distinct case and gets a named
  refusal.** Go's interfaces admit more than Rust's enums, which produced three
  aliasing and nil bugs in P-002 before the value model was re-derived; the
  dispatcher now refuses anything outside the six types by name.
- Map iteration order may never reach an output. Sort keys explicitly, by the
  rule [`serialization.md`](spec/serialization.md) §1 states — which is UTF-16
  code unit order, and **not** Go's byte-wise string comparison. That difference
  has already caused one divergence in this repository.
