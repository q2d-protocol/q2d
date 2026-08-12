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
import tempfile
import unittest
from pathlib import Path

CONFORMANCE = Path(__file__).resolve().parents[1]
HARNESS = CONFORMANCE / "harness"
REPO = CONFORMANCE.parent

STDLIB = Path(sysconfig.get_paths()["stdlib"]).resolve()

# Where installed packages live. On most layouts `site-packages` sits *under*
# the stdlib directory -- `lib/python3.12/site-packages` -- so "inside the
# stdlib path" is not the same question as "part of the standard library", and
# a check that asked only the first would accept every installed package.
INSTALLED = {Path(path).resolve()
             for key in ("purelib", "platlib")
             for path in [sysconfig.get_paths().get(key)] if path}

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


def under(path: Path, root: Path) -> bool:
    """Is `path` inside `root`?

    By path components, not by string prefix: `spec-backup` starts with `spec`
    and is a different directory, and a check that could not tell them apart
    would accept the one thing it exists to reject.
    """
    resolved = path.resolve()
    return resolved == root or root in resolved.parents


def is_stdlib(path: Path) -> bool:
    """Is this file part of the standard library, rather than merely near it?

    Two conditions, because either alone is wrong. `site-packages` is usually
    *inside* the stdlib directory, so containment alone accepts every installed
    package; and a virtualenv puts `site-packages` somewhere else entirely, so
    the name alone misses nothing but proves nothing either.
    """
    resolved = path.resolve()
    if any(under(resolved, installed) for installed in INSTALLED):
        return False
    if "site-packages" in resolved.parts or "dist-packages" in resolved.parts:
        return False
    return under(resolved, STDLIB)


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
            if node.level == 1:
                # `from . import corpus` names siblings as its aliases;
                # `from .corpus import Vector` names one as its module. Both go
                # through the same check as everything else -- dropping them
                # would let `from .bindings import sign` past, and a file named
                # `bindings.py` dropped into the harness directory is a sibling
                # by this test's definition only until somebody looks at it.
                if node.module:
                    names.add(node.module.split(".")[0])
                else:
                    names.update(alias.name.split(".")[0] for alias in node.names)
                continue
            if node.level > 1:
                # `from .. import x` reaches *outside* the harness directory,
                # which is the thing this file exists to forbid. Reported under
                # a name no resolver will accept, so it fails loudly rather
                # than being dropped as unrecognised.
                names.add("." * node.level + (node.module or ""))
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def import_problem(name: str, siblings: set[str]) -> str | None:
    """Why the harness may not import `name`, or None if it may.

    A function rather than assertions inline in a test, so the negative test
    below can run the same code over a module that *should* be rejected. A
    negative test that only checks the name extraction would keep passing if
    this rule were relaxed, which is the failure mode of a check nobody
    exercises.
    """
    if name in siblings:
        return None

    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError) as exc:
        # A relative import reaching outside the harness, or a name no resolver
        # will take. Returned rather than raised: this sweep reports on every
        # module, and one that dies partway hides the rest.
        return (f"imports {name!r}, which does not resolve ({exc}). Every "
                f"import must be stdlib or a sibling module")

    if spec is None:
        return (f"imports {name!r}, which does not resolve — the harness must "
                f"run on a bare Python")

    if spec.origin in NOT_A_FILE:
        # A namespace package (PEP 420) has no origin of its own but does have
        # search locations, and a third-party one's locations are in
        # site-packages. Accepting every origin-less spec as a built-in would
        # let exactly that past.
        locations = list(getattr(spec, "submodule_search_locations", None) or [])
        outside = [place for place in locations if not is_stdlib(Path(place))]
        if outside:
            return (f"imports {name!r}, a namespace package with locations "
                    f"outside the standard library ({outside[0]})")
        return None

    origin = Path(spec.origin).resolve()
    if not is_stdlib(origin):
        return (f"imports {name!r} from {origin}, which is outside the standard "
                f"library. The harness is stdlib-only: a package shared with one "
                f"implementation and not the other reintroduces the common-mode "
                f"bug the third language rules out")
    return None


class ImportTest(unittest.TestCase):
    def test_every_import_is_stdlib_or_a_sibling(self):
        siblings = {path.stem for path in harness_modules()}

        for module in harness_modules():
            for name in sorted(imported_names(module.read_text(encoding="utf-8"))):
                with self.subTest(module=module.name, imports=name):
                    problem = import_problem(name, siblings)
                    self.assertIsNone(
                        problem,
                        f"{module.name} {problem} (P-001 §9, decision 2)")

    def test_an_added_dependency_is_rejected(self):
        # The real rejection path, over a real module outside the standard
        # library -- written to a temporary directory and put on the path,
        # which is what installing a binding built from an implementation would
        # amount to. Asserting only that the *name* was extracted would keep
        # passing if this rule were later relaxed.
        with tempfile.TemporaryDirectory(prefix="q2d-dep-") as tmp:
            (Path(tmp) / "q2d_pretend_binding.py").write_text("", encoding="utf-8")
            sys.path.insert(0, tmp)
            importlib.invalidate_caches()
            try:
                problem = import_problem("q2d_pretend_binding", set())
            finally:
                sys.path.remove(tmp)
                importlib.invalidate_caches()

        self.assertIsNotNone(problem, "a module outside the standard library "
                                      "was accepted; the check is not checking")
        self.assertIn("outside the standard library", problem)

    def test_a_namespace_package_inside_the_stdlib_tree_is_rejected(self):
        # The shape that makes containment alone wrong: a PEP 420 namespace
        # package installed under `lib/pythonX.Y/site-packages`, which *is*
        # inside the stdlib directory on most layouts. Built where site-packages
        # actually is, rather than assumed.
        base = next(iter(INSTALLED), None) or (STDLIB / "site-packages")
        self.assertFalse(is_stdlib(base / "vendor" / "thing.py"),
                         f"{base} was accepted as standard library")
        self.assertFalse(is_stdlib(STDLIB / "site-packages" / "thing.py"),
                         "site-packages under the stdlib path was accepted")
        self.assertTrue(is_stdlib(STDLIB / "json" / "__init__.py"),
                        "the standard library was not recognised")

    def test_a_name_that_resolves_to_nothing_is_rejected(self):
        problem = import_problem("q2d_core_binding_that_does_not_exist", set())
        self.assertIsNotNone(problem)
        self.assertIn("does not resolve", problem)

    def test_an_import_is_found_wherever_it_is_written(self):
        # Extraction, separately from the verdict: an import inside a function
        # or a `try` block is the same dependency, and is where one would end
        # up if somebody wanted it to look optional.
        names = imported_names("import json\n"
                              "def f():\n"
                              "    try:\n"
                              "        import q2d_core\n"
                              "    except ImportError:\n"
                              "        from cryptography import x\n"
                              "from .. import bindings\n"
                              "from . import corpus\n")
        # `from . import corpus` names a sibling, and is extracted like any
        # other so the sibling rule -- rather than this function -- is what
        # accepts it. `from .. import` reaches outside the harness directory and
        # is reported under a name that resolves to nothing, so it fails rather
        # than being dropped.
        self.assertEqual(names,
                         {"json", "q2d_core", "cryptography", "corpus", ".."})
        self.assertIsNone(import_problem("corpus", {"corpus"}))
        self.assertIsNotNone(import_problem("bindings", {"corpus"}))


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
                try:
                    module = importlib.import_module(module_file.stem)
                except Exception as exc:
                    # A module that will not import has a problem the import
                    # test above names precisely. Reported here rather than
                    # raised, so this sweep still covers every other module --
                    # one broken file must not hide the rest.
                    self.fail(f"{module_file.name} could not be imported "
                              f"({exc}); see test_every_import_is_stdlib_or_a_"
                              f"sibling for what it depends on")
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
                            any(under(value, root) for root in allowed),
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
