"""The harness depends on neither implementation (P-001 issue 15).

    python3 -m unittest discover -s conformance/tests

[P-001](../../docs/prds/P-001-conformance-corpus.md) §9 makes this
escalate-if-changed, and says why: *"Shared code means shared bugs that cancel
out."* A canonicalization or digest error present in both the harness and an
implementation would agree with itself, and every vector exercising it would
pass. A third language makes that impossible by construction — but only while
nothing quietly reintroduces the dependency, which is what §7 means by
*"asserted by dependency check, not by convention"*.

Three ways the dependency could come back, and each is checked:

- **An import.** A Python binding built from the Rust crate would be an
  ordinary `import`, and would look like any other line.
- **A path.** Reading a file out of `src/`, or shelling out to a hardcoded
  `target/debug/…`, is the same coupling without an import statement. The
  runner path is an *argument* for this reason.
- **A third-party package.** Not an implementation, but the same failure with
  more steps: a JSON or crypto library shared with one implementation and not
  the other reintroduces exactly the common-mode bug the third language exists
  to rule out. The harness is stdlib-only.

Resolving each import rather than matching names against a list: a list is a
convention, which is the thing this test exists to replace. It also has to work
on the Python already present rather than the newest one, so it cannot use
`sys.stdlib_module_names` (3.10+) — CI pins 3.12 and a contributor's machine
may not.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
import sysconfig
import unittest
from pathlib import Path

CONFORMANCE = Path(__file__).resolve().parents[1]
HARNESS = CONFORMANCE / "harness"
REPO = CONFORMANCE.parent

STDLIB = Path(sysconfig.get_paths()["stdlib"]).resolve()

# Origins `importlib` reports for modules with no file of their own.
NOT_A_FILE = ("built-in", "frozen", None)

# Path components that belong to an implementation rather than to the corpus. A
# harness that names one has coupled itself to a build layout at best, and to an
# implementation's internals at worst.
#
# Matched as *components* of a string literal rather than as substrings of the
# file: `src/lib.rs`, `../src`, and `Path("src")` are the same coupling written
# three ways, and a substring search for `/src/` finds none of them. Prose in a
# comment is not a dependency, so only string literals are examined.
IMPLEMENTATION_COMPONENTS = {"src", "target", "go.mod", "q2d-core"}

# And suffixes: a harness naming a file of either implementation is coupled to
# it whatever directory it sits in.
IMPLEMENTATION_SUFFIXES = (".rs", ".go", ".toml")


def harness_modules() -> list[Path]:
    modules = sorted(HARNESS.glob("*.py"))
    if not modules:
        raise AssertionError(f"no harness modules found under {HARNESS}; "
                             f"this test would pass vacuously")
    return modules


def imported_names(source: str) -> set[str]:
    """Every module a file imports, at any depth.

    `ast.walk` rather than reading the top of the file: an import inside a
    function or a `try` block is the same dependency, and is where one would
    end up if somebody wanted it to look optional.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # A relative import can only reach a sibling, which is covered
                # by the sibling rule below.
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


class ImportTest(unittest.TestCase):
    def test_every_import_is_stdlib_or_a_sibling(self):
        siblings = {path.stem for path in harness_modules()}

        for module in harness_modules():
            for name in sorted(imported_names(module.read_text(encoding="utf-8"))):
                with self.subTest(module=module.name, imports=name):
                    if name in siblings:
                        continue

                    spec = importlib.util.find_spec(name)
                    self.assertIsNotNone(
                        spec, f"{module.name} imports {name!r}, which does not "
                              f"resolve — the harness must run on a bare Python")

                    if spec.origin in NOT_A_FILE:
                        continue

                    origin = Path(spec.origin).resolve()
                    self.assertTrue(
                        str(origin).startswith(str(STDLIB)),
                        f"{module.name} imports {name!r} from {origin}, which is "
                        f"outside the standard library. The harness is "
                        f"stdlib-only: a package shared with one implementation "
                        f"and not the other reintroduces the common-mode bug "
                        f"the third language rules out (P-001 §9.2)")
                    self.assertNotIn(
                        "site-packages", origin.parts,
                        f"{module.name} imports {name!r} from site-packages")

    def test_the_check_would_notice_an_added_dependency(self):
        # The check above passes on a harness that imports nothing at all, so
        # it is worth showing it fails on something. Not a mock: the same
        # function, over a file that does what a future contributor would do.
        names = imported_names("import json\n"
                              "def f():\n"
                              "    try:\n"
                              "        import q2d_core\n"
                              "    except ImportError:\n"
                              "        from cryptography import x\n")
        self.assertEqual(names, {"json", "q2d_core", "cryptography"})
        # Deliberately no assertion about whether those modules are installed.
        # A contributor may legitimately have an implementation binding on their
        # machine; what this check forbids is the *harness* importing one, and a
        # test that also failed on what happens to be installed would be red for
        # a reason that is nobody's mistake.


class PathTest(unittest.TestCase):
    def test_no_harness_module_names_an_implementation_path(self):
        # An import is not the only way to depend on an implementation. Reading
        # a file out of its tree, or shelling out to a built binary at a fixed
        # path, is the same coupling with no import statement to find. The
        # runner path is an argument for this reason (§4.7).
        for module in harness_modules():
            tree = ast.parse(module.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                literal = node.value
                components = {part for part in literal.replace("\\", "/").split("/")
                              if part not in ("", ".", "..")}
                named = sorted(components & IMPLEMENTATION_COMPONENTS)
                if literal.endswith(IMPLEMENTATION_SUFFIXES):
                    named.append(literal)
                if not named:
                    continue
                # `self.fail` rather than `assertEqual(named, [], message)`: an
                # f-string message is built before the assertion runs, so a
                # message naming `named[0]` raises IndexError on every literal
                # that passes. A check must not crash on the input it exists to
                # accept any more than on the input it exists to reject.
                with self.subTest(module=module.name, line=node.lineno):
                    self.fail(
                        f"{module.name}:{node.lineno} names {named[0]!r} in "
                        f"{literal!r}. The harness takes a runner as an "
                        f"argument and knows nothing about where one is built "
                        f"or what it is written in (P-001 §4.7)")

    def test_every_path_the_harness_holds_is_under_conformance_or_spec(self):
        # `lint` and `coverage` read `spec/claims.md` and
        # `spec/conformance-classes.md` -- the identifiers are declared there,
        # and restating them here would be a second source of truth. Nothing
        # else outside `conformance/` is read.
        #
        # Checked by importing each module and looking at the paths it actually
        # holds, rather than by pattern-matching string literals: a JSON
        # Pointer starts with `/` and is not a filesystem path, and a check
        # that guesses is one somebody eventually silences.
        sys.path.insert(0, str(HARNESS))
        try:
            import lint as lint_module

            # Read from `lint` rather than restated here: the citable
            # directories are its list, and a copy in a test is a second source
            # of truth that drifts the first time one is added.
            allowed = [CONFORMANCE]
            allowed += [REPO / directory for directory in lint_module.CITABLE_DIRS]

            checked = 0
            for module_file in harness_modules():
                if module_file.stem == "__main__":
                    continue
                module = importlib.import_module(module_file.stem)
                for name, value in vars(module).items():
                    if not isinstance(value, Path):
                        continue
                    checked += 1
                    with self.subTest(module=module_file.name, constant=name):
                        if value.resolve() == REPO:
                            # A base the paths above are built from, not
                            # something read. Every path derived from it is
                            # checked on its own line.
                            continue
                        self.assertTrue(
                            any(str(value.resolve()).startswith(str(root))
                                for root in allowed),
                            f"{module_file.name}.{name} is {value}, outside "
                            f"conformance/ and the citable directories "
                            f"({', '.join(lint_module.CITABLE_DIRS)}) — "
                            f"P-001 §4.7")
                        self.assertTrue(
                            value.exists(),
                            f"{module_file.name}.{name} points at {value}, "
                            f"which does not exist")
            self.assertGreater(checked, 0,
                               "no paths were checked; this test would pass "
                               "over a harness that had stopped holding any")
        finally:
            sys.path.remove(str(HARNESS))


if __name__ == "__main__":
    unittest.main()
