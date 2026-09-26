"""Black-box provenance cases; fixture repositories never touch real core."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "src"


class DoctorCases(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.reference = self.make_core("reference")

    def make_core(self, name):
        root = self.root / name
        package = root / "src/plotsrv"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text('"""Inert test candidate."""\n')
        (root / "pyproject.toml").write_text('[project]\nname = "plotsrv"\nversion = "1.0"\n')
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run([
            "git", "-C", str(root), "-c", "user.name=Doctor Test",
            "-c", "user.email=doctor@example.invalid", "-c", "core.hooksPath=/dev/null",
            "commit", "-qm", "fixture",
        ], check=True)
        return root

    def run_doctor(self, reference, candidate):
        # -S prevents the developer's installed candidate affecting these fixtures.
        env = {**os.environ, "PLOTSRV_CORE_DIR": str(reference),
               "PYTHONPATH": os.pathsep.join([str(SOURCE), str(candidate / "src")])}
        process = subprocess.run(
            [sys.executable, "-B", "-S", "-m", "plotsrv_examples", "doctor"],
            env=env, capture_output=True, text=True, timeout=30,
        )
        return process.returncode, json.loads(process.stdout)

    def test_matching_source_and_no_core_writes(self):
        before = {p.relative_to(self.reference): p.read_bytes()
                  for p in self.reference.rglob("*") if p.is_file()}
        code, result = self.run_doctor(self.reference, self.reference)
        self.assertEqual(code, 0)
        self.assertEqual(result["relationship"], "matching source checkout")
        self.assertIsNone(result["runtime_candidate"]["version"])
        after = {p.relative_to(self.reference): p.read_bytes()
                 for p in self.reference.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_different_candidate(self):
        candidate = self.make_core("other")
        code, result = self.run_doctor(self.reference, candidate)
        self.assertEqual(code, 1)
        self.assertEqual(result["readiness"], "blocked")
        self.assertEqual(result["runtime_candidate"]["checkout"]["path"], str(candidate))
        self.assertIn("does not match", " ".join(result["problems"]))

    def test_missing_reference(self):
        code, result = self.run_doctor(self.root / "absent", self.reference)
        self.assertEqual(code, 1)
        self.assertIn("Core reference unavailable", " ".join(result["problems"]))
        self.assertIn("module", result["runtime_candidate"])

    def test_empty_override_does_not_fall_back(self):
        code, result = self.run_doctor("", self.reference)
        self.assertEqual(code, 1)
        self.assertIn("PLOTSRV_CORE_DIR is empty", " ".join(result["problems"]))

    def test_missing_runtime(self):
        code, result = self.run_doctor(self.reference, self.root / "absent")
        self.assertEqual(code, 1)
        self.assertEqual(result["relationship"], "unverified")
        self.assertIn("Runtime candidate unavailable", " ".join(result["problems"]))


if __name__ == "__main__":
    unittest.main()
