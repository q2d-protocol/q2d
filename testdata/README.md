# Three-way serialization fixture

`canonical-query.json` is the query
[`tools/author_message.py`](../tools/author_message.py) signs — every field
[`core-model.md`](../spec/core-model.md) §2 marks required, and no optional one.
`canonical-query.serialized` is what
[P-002](../docs/prds/P-002-message-envelope.md) §4.2's production profile makes
of it.

**Three implementations are held to those exact bytes**, in three languages, by
three tests that do not share code:

| Implementation | Test |
|---|---|
| Python — [`tools/author_vectors.py`](../tools/author_vectors.py) | [`conformance/tests/test_canonical_query.py`](../conformance/tests/test_canonical_query.py) |
| Rust — [`src/value.rs`](../src/value.rs) | `cargo test canonical` |
| Go — [`value.go`](../value.go) | `go test -run Canonical` |

P-002 §7's first acceptance criterion is that both implementations serialize the
same logical query to byte-identical output. This is that criterion with the
authoring tool added as a third reading — and the third one matters, because the
corpus's expected bytes come from it. Two implementations agreeing with each
other but not with the corpus would pass every vector and be wrong.

The Python side is what generates both files, so it cannot fail its own check by
construction. It is asserted anyway: the check that would fail is somebody
regenerating the fixture from a changed serializer without noticing that the
other two no longer match.
