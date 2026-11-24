"""The checker run shown at the top of the README matches a real run."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "readme-workshop" / "scripts" / "check_readme.py"


class ReadmeExample(unittest.TestCase):
    def test_saved_output_matches_a_real_run(self):
        done = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), "--root", "tests/fixtures/check/mcp-server",
                               "--readme", "README-bad.md"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 1, done.stderr)
        saved = (ROOT / "docs" / "check-example.txt").read_text(encoding="utf-8")
        self.assertEqual(done.stdout.replace("\r\n", "\n"), saved)


if __name__ == "__main__":
    unittest.main()
