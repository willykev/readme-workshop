"""Shape of the skill folder: frontmatter, size, references, portability."""
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "readme-workshop"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import formats  # noqa: E402

ALLOWED_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
HOST_ONLY = ("${CLAUDE_SKILL_DIR}", "${CLAUDE_PLUGIN_ROOT}", "$ARGUMENTS", "AskUserQuestion")


def md_links(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text)


class SkillShape(unittest.TestCase):
    def setUp(self):
        self.text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.meta, self.body, certain = formats.frontmatter(self.text)
        self.assertTrue(certain, "frontmatter must parse with certainty")

    def test_frontmatter_fields(self):
        self.assertEqual(set(self.meta) - ALLOWED_FIELDS, set())
        self.assertEqual(self.meta["name"], SKILL_DIR.name)
        self.assertRegex(self.meta["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(self.meta["name"]), 64)
        self.assertLessEqual(len(self.meta["description"]), 1024)
        self.assertGreater(len(self.meta["description"]), 200)
        self.assertLessEqual(len(self.meta.get("compatibility", "")), 500)

    def test_size(self):
        self.assertLessEqual(len(self.text.splitlines()), 250)

    def test_every_reference_linked_one_hop(self):
        linked = {os.path.normpath(l).replace(os.sep, "/") for l in md_links(self.body) if not l.startswith("http")}
        for p in linked:
            self.assertTrue((SKILL_DIR / p).exists(), f"SKILL.md links to missing {p}")
        refs = {f"references/{p.name}" for p in (SKILL_DIR / "references").glob("*.md")}
        self.assertEqual(refs - linked, set(), "references not linked from SKILL.md")

    def test_references_link_only_inside_the_skill(self):
        for p in (SKILL_DIR / "references").glob("*.md"):
            for link in md_links(p.read_text(encoding="utf-8")):
                if link.startswith(("http://", "https://")):
                    continue
                target = (p.parent / link).resolve()
                self.assertTrue(str(target).startswith(str(SKILL_DIR)), f"{p.name} links outside: {link}")
                self.assertTrue(target.exists(), f"{p.name} links to missing {link}")

    def test_long_references_have_contents(self):
        for p in (SKILL_DIR / "references").glob("*.md"):
            lines = p.read_text(encoding="utf-8").splitlines()
            if len(lines) > 100:
                self.assertTrue(any(l.startswith("Contents:") for l in lines[:6]), f"{p.name} needs a contents line")

    def test_no_host_only_syntax(self):
        for p in [SKILL_DIR / "SKILL.md", *(SKILL_DIR / "references").glob("*.md")]:
            text = p.read_text(encoding="utf-8")
            for token in HOST_ONLY:
                self.assertNotIn(token, text, f"{p.name} uses host-only {token}")

    def test_scripts_named_in_skill_exist(self):
        for name in re.findall(r"scripts/([a-z_]+\.py)", self.text):
            self.assertTrue((SKILL_DIR / "scripts" / name).exists(), name)

    def test_license_inside_skill(self):
        self.assertTrue((SKILL_DIR / "LICENSE").exists())


class PrivateTerms(unittest.TestCase):
    """Optional leak check: READMEWS_PRIVATE_TERMS names a file of terms, one per line."""

    def test_no_private_terms(self):
        path = os.environ.get("READMEWS_PRIVATE_TERMS")
        if not path:
            self.skipTest("READMEWS_PRIVATE_TERMS not set")
        # "md:term" lines apply to Markdown prose only (a term that is fine in detection code)
        terms = [t.strip() for t in Path(path).read_text().splitlines() if t.strip() and not t.startswith("#")]
        hits = []
        for p in ROOT.rglob("*"):
            if ".git" in p.parts or not p.is_file() or p.suffix in {".png", ".gif", ".jpg", ".pyc"}:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore").lower()
            for t in terms:
                prose_only = t.startswith("md:")
                term = t[3:] if prose_only else t
                if prose_only and p.suffix != ".md":
                    continue
                if term.lower() in text:
                    hits.append(f"{p.relative_to(ROOT)}: {term}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
