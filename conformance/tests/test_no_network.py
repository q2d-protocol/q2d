"""Neither implementation can reach the network (P-005 issue 9).

    python3 -m unittest discover -s conformance/tests

[P-005](../../docs/prds/P-005-registry-client.md) §4.3 forbids automatic
refresh of the predicate manifest, and §8 asks for it *"asserted by dependency
check"* rather than by a rule someone follows:

> The registry client having no network dependency at all is stronger than a
> rule saying it must not fetch.

The rule it replaces is not a small one. An automatic update path is a
remote-controlled redefinition of what a custodian considers bounded — even
signed and digest-checked, it moves the authorization decision from the
operator to whoever controls the channel. A check that the capability is absent
cannot be forgotten the way a convention can.

## Two scopes, because the two languages localise differently

**Per file**, for `src/registry.rs` and `registry.go`: what the registry client
itself reaches for. This is the direct reading of the issue.

**Whole implementation**, for the dependency sets: a networking crate in
`Cargo.lock`, or a module in `go.mod`, is a capability linked into the binary
whatever imports it. Go's standard library is always available, so `go.mod`
cannot show `net/http` — which is exactly why the per-file import check exists
alongside it, and why the package-wide sweep below is the one that would catch
a helper added in a neighbouring file.

## This will need scoping when P-013 lands

[P-013](../../docs/prds/P-013-https-binding.md) is the HTTPS binding, and it
will link a server. The package-wide assertions here are true today and are
**deliberately not written as a permanent claim about the whole repository** —
when the binding arrives, the right change is to narrow them to the registry's
own files and to whatever crate or package the binding does not share, not to
delete them. That is said here rather than left for someone to infer from a
failing test.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Anything that can open a socket. Names rather than behaviour, which is the
# honest limit of a static check: it catches the ways a network client is
# normally acquired, not a hand-rolled one over a raw file descriptor.
#
# Rust's standard library networking is `std::net`; the rest are the crates a
# Rust or Go program reaches for. `crypto/tls` is here because a TLS client
# without a socket is not a thing anyone builds.
# Rust splits into two questions with two right answers, which the first version
# of this file conflated and paid for: whole-file substring matching found `surf`
# inside a word in `base64url.rs`, and missed `use std::{fmt, net::TcpStream}`
# because the literal `std::net` is not in it.
#
# **Crates are a lock-file question** and are covered by the allowlist below —
# authoritatively, since a crate is linked whether or not any file names it.
# **Standard-library networking is a source question**, and `net::` is the path
# segment every spelling of it goes through: `std::net::TcpStream`, a
# brace-grouped `std::{net::…}`, and a fully-qualified call all contain it.
NETWORK_RUST_SOURCE = (r"\bstd::net\b", r"\bnet::")
NETWORK_GO = ("net", "net/http", "net/url", "crypto/tls", "golang.org/x/net")


def reaches_network_go(import_path: str) -> str | None:
    """The banned prefix this import path is under, or `None`.

    Prefix rather than exact match, so `golang.org/x/net/http2` is caught by
    `golang.org/x/net` — and prefix **on a path boundary** rather than substring,
    so a module called `magnet` is not. The first version compared for equality
    and would have missed every sub-package.
    """
    for banned in NETWORK_GO:
        if import_path == banned or import_path.startswith(banned + "/"):
            return banned
    return None


def rust_reaches_network(path: Path) -> str | None:
    """The banned path this file names anywhere, or `None`.

    The **whole file**, not its `use` lines. Review found that reading only
    `use x;` misses `use std::{net::TcpStream}` and misses a fully-qualified
    `std::net::TcpStream::connect(...)` entirely — and a check that passes while
    the capability is one line away is worse than none, because it is cited.
    """
    text = path.read_text(encoding="utf-8")
    for pattern in NETWORK_RUST_SOURCE:
        if re.search(pattern, text):
            return pattern
    return None


def go_imports(path: Path) -> set[str]:
    """Every path this Go file imports.

    **Every** import declaration, not the first: Go permits more than one, and
    reading only the first would let a later `import ("net/http")` through.
    Review found that.

    Import blocks and single-line imports only, so a quoted string in a comment
    or a message is not mistaken for one.
    """
    text = path.read_text(encoding="utf-8")
    found = set(re.findall(r'^import (?:[\w.]+\s+)?"([^"]+)"', text, re.M))
    for block in re.finditer(r"^import \(\n(.*?)^\)", text, re.S | re.M):
        found |= set(re.findall(r'"([^"]+)"', block.group(1)))
    return found


class RegistryClientTest(unittest.TestCase):
    """The direct reading of the issue: what the client itself reaches for."""

    def test_the_rust_registry_module_reaches_for_no_network(self):
        self.assertIsNone(rust_reaches_network(REPO / "src" / "registry.rs"))

    def test_the_go_registry_file_imports_no_network(self):
        imported = go_imports(REPO / "registry.go")
        self.assertIn("fmt", imported, "the import reader found nothing, so it proves nothing")
        for import_path in imported:
            self.assertIsNone(
                reaches_network_go(import_path), f"registry.go imports {import_path}"
            )


class ImplementationTest(unittest.TestCase):
    """The wider reading: a capability linked in is reachable from anywhere.

    Package-wide for Go because the whole implementation is one package, so a
    neighbouring file's import is available to the registry client without an
    import of its own. Crate-wide for Rust for the same reason.
    """

    def test_no_rust_source_file_reaches_for_the_network(self):
        checked = 0
        for path in sorted((REPO / "src").rglob("*.rs")):
            found = rust_reaches_network(path)
            self.assertIsNone(found, f"{path.name} names {found}")
            checked += 1
        self.assertGreater(checked, 10, "the sweep found almost no files, so it proves little")

    def test_no_go_source_file_imports_the_network(self):
        checked = 0
        for path in sorted(REPO.glob("*.go")):
            for import_path in go_imports(path):
                self.assertIsNone(
                    reaches_network_go(import_path), f"{path.name} imports {import_path}"
                )
            checked += 1
        self.assertGreater(checked, 10, "the sweep found almost no files, so it proves little")

    def test_the_locked_crate_set_is_exactly_what_is_expected(self):
        # **An allowlist, not a denylist**, which is what lets the claim be about
        # *transitive* dependencies at all. A denylist covers the crates someone
        # thought of, so review was right that the row overclaimed: a networking
        # crate nobody listed would have passed.
        #
        # The same reasoning as the corpus projection's field allowlist. The cost
        # is that this list changes when `ed25519-dalek`'s tree does, and that is
        # the feature: a new transitive dependency in a repository whose stated
        # posture is *one dependency* should be a decision somebody makes, not a
        # lock-file diff nobody reads.
        expected = {
            "block-buffer", "cfg-if", "cpufeatures", "crypto-common",
            "curve25519-dalek", "curve25519-dalek-derive", "digest", "ed25519",
            "ed25519-dalek", "fiat-crypto", "hybrid-array", "libc", "proc-macro2",
            "q2d", "quote", "rustc_version", "semver", "sha2", "signature",
            "subtle", "syn", "typenum", "unicode-ident",
        }
        locked = set(
            re.findall(r'^name = "([^"]+)"', (REPO / "Cargo.lock").read_text("utf-8"), re.M)
        )
        self.assertIn("ed25519-dalek", locked, "the lock file did not parse as expected")
        self.assertEqual(
            locked,
            expected,
            "the locked crate set changed; CONVENTIONS-rust.md §2's posture is one "
            "dependency, so read what arrived before updating this list",
        )

    def test_the_go_module_requires_no_network_package(self):
        # Weaker than the Rust half by construction and worth saying so: Go's
        # standard library is always available, so `go.mod` can never show
        # `net/http`. The per-file sweep above is what covers that, and this
        # covers a third-party client arriving as a module.
        # Both spellings: `require x v1.2.3` on one line, and the indented form
        # inside a `require (` block. The first version of this pattern read only
        # the block form and found nothing — caught by the guard below, which is
        # what that guard is for.
        required = re.findall(
            r"^(?:require\s+|\s+)([\w./-]+)\s+v", (REPO / "go.mod").read_text("utf-8"), re.M
        )
        self.assertIn("filippo.io/edwards25519", required, "go.mod did not parse as expected")
        for module in required:
            self.assertIsNone(reaches_network_go(module), f"go.mod requires {module}")


class ReaderTest(unittest.TestCase):
    """The checks above are worth only as much as the readers under them.

    A check that does not crash on the input it exists to reject is one rule;
    a check that silently reads *nothing* is the same failure quieter, and it is
    the one that has bitten this repository. Both readers are given a file that
    does import the network, and must find it.
    """

    def test_the_rust_reader_finds_every_shape_of_network_use(self):
        import tempfile

        # The three shapes review named. The first is what the reader used to
        # handle; the other two are why it now reads the whole file.
        for source in (
            "use std::net::TcpStream;\n",
            "use std::{fmt, net::TcpStream};\n",
            "fn f() { let _ = std::net::TcpStream::connect(\"x\"); }\n",
        ):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "fake.rs"
                path.write_text(source, encoding="utf-8")
                self.assertIsNotNone(rust_reaches_network(path), source)

        # And prose that merely contains the letters is not a finding. The
        # first version failed `base64url.rs` on the word *surface*, and the
        # tempting fix there is to weaken the check rather than to sharpen it.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clean.rs"
            path.write_text(
                "use std::fmt;\n// the attack surface here is a magnet for tokenizers\n",
                encoding="utf-8",
            )
            self.assertIsNone(rust_reaches_network(path))

    def test_the_go_reader_finds_a_network_import(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fake.go"
            path.write_text(
                'package q2d\n\nimport (\n\t"fmt"\n\t"net/http"\n)\n\nvar _ = fmt.Sprint\n',
                encoding="utf-8",
            )
            imported = go_imports(path)
            self.assertIn("net/http", imported)
            self.assertIn("fmt", imported)

    def test_a_sub_package_of_a_banned_path_is_caught_and_a_lookalike_is_not(self):
        # Prefix on a path boundary. Exact matching would have missed every
        # sub-package, and plain substring matching would fail a module called
        # `magnet` — which is the shape of fix someone applies by weakening the
        # check.
        self.assertEqual(reaches_network_go("net/http"), "net")
        self.assertEqual(reaches_network_go("golang.org/x/net/http2"), "golang.org/x/net")
        self.assertIsNone(reaches_network_go("example.com/magnet"))
        self.assertIsNone(reaches_network_go("fmt"))

    def test_the_go_reader_finds_a_second_import_block(self):
        # Go permits more than one import declaration, and reading only the first
        # would let a later block through. Review found that.
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fake.go"
            path.write_text(
                'package q2d\n\nimport (\n\t"fmt"\n)\n\nimport (\n\t"net/http"\n)\n',
                encoding="utf-8",
            )
            imported = go_imports(path)
            self.assertIn("fmt", imported)
            self.assertIn("net/http", imported)

    def test_the_go_reader_ignores_a_quoted_string_outside_an_import(self):
        # Otherwise every file mentioning "net/http" in a comment or a message
        # would fail, and the fix would be to weaken the check.
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fake.go"
            path.write_text(
                'package q2d\n\nimport "fmt"\n\nvar note = "net/http is not imported here"\n'
                "var _ = fmt.Sprint\n",
                encoding="utf-8",
            )
            imported = go_imports(path)
            self.assertIn("fmt", imported)
            self.assertNotIn("net/http", imported)


if __name__ == "__main__":
    unittest.main()
