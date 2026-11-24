"""The plugin manifests agree with each other and with VERSION."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


class Manifests(unittest.TestCase):
    def setUp(self):
        self.version = (ROOT / "VERSION").read_text().strip()
        self.root = load("plugin.json")
        self.claude = load(".claude-plugin/plugin.json")
        self.market = load(".claude-plugin/marketplace.json")

    def test_identity_and_version(self):
        for m in (self.root, self.claude):
            self.assertEqual(m["name"], "readme-workshop")
            self.assertEqual(m["version"], self.version)
        self.assertEqual(self.root["description"], self.claude["description"])
        self.assertEqual(self.root["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")

    def test_marketplace_entry(self):
        self.assertTrue(self.market["name"])
        self.assertTrue(self.market["owner"]["name"])
        self.assertTrue(self.market.get("description"))
        entries = [p for p in self.market["plugins"] if p["name"] == self.claude["name"]]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "./")

    def test_skill_matches(self):
        skill = ROOT / "skills" / self.root["name"] / "SKILL.md"
        self.assertTrue(skill.exists())

    def test_changelog_has_version(self):
        changelog = ROOT / "CHANGELOG.md"
        if changelog.exists():
            self.assertIn(self.version, changelog.read_text())


if __name__ == "__main__":
    unittest.main()
