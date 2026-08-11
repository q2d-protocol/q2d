"""The harness CLI, and what it must do about the modes that do not exist yet.

    python3 -m unittest discover -s conformance/tests

P-001 §7 wants a harness that reports fail because no implementation exists. A
mode that is not built must therefore say so and exit non-zero -- one that
printed nothing and returned 0 would be indistinguishable from a mode that ran
and found nothing wrong, which is the more expensive of the two failures.

These tests turn red the day someone builds one of those modes, which is the
moment to decide how CI asserts its expected state. `.github/workflows/checks.yml`
carries that rule for when it applies: assert fail-all, rather than run a check
that is red by design until Stage 1 lands. Nothing asserts fail-all yet, because
there is no `run` mode to assert it about -- this file is the placeholder that
makes its absence visible.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"

# Mode, and the issue that owns building it.
UNBUILT = [("cross", "issue 9"), ("coverage", "issue 6")]


def harness(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HARNESS), *args],
                          capture_output=True, text=True)


class UnbuiltModeTest(unittest.TestCase):
    def test_unbuilt_modes_fail_loudly(self):
        for mode, issue in UNBUILT:
            with self.subTest(mode=mode):
                result = harness(mode)
                self.assertNotEqual(result.returncode, 0,
                                    f"harness {mode} succeeded without being built")
                self.assertIn("not built yet", result.stderr)
                self.assertIn(issue, result.stderr,
                              f"harness {mode} does not name the issue that owns it")

    def test_unknown_mode_fails(self):
        result = harness("frobnicate")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown mode", result.stderr)


class BuiltModeTest(unittest.TestCase):
    def test_lint_runs(self):
        result = harness("lint")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_run_requires_something_to_run_against(self):
        # Not an unbuilt mode: it is built, and refuses to guess which runner
        # was meant.
        result = harness("run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--impl is required", result.stderr)

    def test_an_unknown_flag_is_an_error(self):
        # A typo in a CI invocation must not silently run something else.
        result = harness("lint", "--impll", "x")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected argument", result.stderr)

    def test_help_is_not_an_error(self):
        result = harness("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("lint", result.stdout)

    def test_no_mode_is_an_error(self):
        # Printing usage and returning 0 would make a typo in a CI script look
        # like a passing run.
        result = harness()
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
