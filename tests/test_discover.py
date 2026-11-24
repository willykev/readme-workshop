import builtins
import json
import ntpath
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "skills", "readme-workshop", "scripts")
sys.path.insert(0, SCRIPTS)

import discover  # noqa: E402

from fixturetree import materialize  # noqa: E402
FIXTURES = str(materialize(os.path.join(HERE, "fixtures", "discover")))
SCRIPT = os.path.join(SCRIPTS, "discover.py")
HAS_GIT = shutil.which("git") is not None
TOP_KEYS = {"tool", "version", "root", "truncated", "limits", "files", "skipped", "languages", "manifests", "kinds",
            "entry_points", "surfaces", "channels", "platforms", "signals", "docs", "pictures", "examples", "tests",
            "project_rules", "history"}


def item_names(category, items):
    """The names a surface category reports, in the form expected.json uses."""
    if category == "routes":
        return [f"{i['method']} {i['route']}" for i in items]
    if category == "hooks":
        return [i["event"] for i in items]
    if category == "shortcuts":
        return [i["keys"] for i in items]
    if category == "config":
        return [i["path"] for i in items]
    return [i["name"] for i in items]


def every_name(result):
    """Every name the scan reports as a surface or entry point."""
    names = set()
    for category, items in result["surfaces"].items():
        if isinstance(items, list):
            names.update(item_names(category, items))
            for item in items:
                names.update(item.get("keys", []) if category == "config" else [item.get("name") or ""])
                if category == "routes":
                    names.add(item["route"])
        elif items:
            names.update(items["inputs"])
            names.update(items["outputs"])
    names.update(e["name"] for e in result["entry_points"])
    return names


class FixtureTests(unittest.TestCase):
    """Each fixture is a small project with an expected.json answer and planted decoys."""

    maxDiff = None

    def test_sources_with_windows_line_endings(self):
        # A checkout with CRLF line endings must give the same surfaces as one with LF.
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "mcp-server")
            shutil.copytree(os.path.join(FIXTURES, "mcp-server"), dst)
            for d, _, files in os.walk(dst):
                for f in files:
                    path = os.path.join(d, f)
                    with open(path, "rb") as fh:
                        data = fh.read()
                    with open(path, "wb") as fh:
                        fh.write(data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
            crlf = discover.scan(dst)
        lf = discover.scan(os.path.join(FIXTURES, "mcp-server"))
        self.assertEqual(sorted(t["name"] for t in crlf["surfaces"]["tools"]),
                         sorted(t["name"] for t in lf["surfaces"]["tools"]))
        self.assertTrue(crlf["surfaces"]["tools"])

    def check(self, name):
        root = os.path.join(FIXTURES, name)
        with open(os.path.join(root, "expected.json")) as f:
            expected = json.load(f)
        result = discover.scan(root)
        self.assertEqual(set(result), TOP_KEYS)
        kinds = {(k["kind"], k["subkind"]) for k in result["kinds"]}
        self.assertEqual(kinds, {tuple(k) for k in expected["kinds"]}, "kinds")
        for kind in result["kinds"]:
            self.assertIn(kind["confidence"], ("high", "medium", "low"))
            self.assertTrue(kind["evidence"])
            for ev in kind["evidence"]:
                self.assertTrue(os.path.isfile(os.path.join(root, ev["path"])), ev)
                self.assertGreaterEqual(ev["line"], 1)
                self.assertTrue(ev["why"])
        self.assertEqual({e["name"] for e in result["entry_points"]}, set(expected["entry_points"]), "entry points")
        self.assertEqual({c["channel"] for c in result["channels"]}, set(expected["channels"]), "channels")
        for channel, cname in expected.get("channel_names", {}).items():
            self.assertEqual(next(c["name"] for c in result["channels"] if c["channel"] == channel), cname)
        if "platforms" in expected:
            self.assertEqual({p["platform"] for p in result["platforms"]}, set(expected["platforms"]), "platforms")
        for category, names in expected["surfaces"].items():
            self.assertEqual(sorted(item_names(category, result["surfaces"][category])), sorted(names), category)
        for category, items in result["surfaces"].items():
            for item in items if isinstance(items, list) else []:
                path = os.path.join(root, item["path"])
                self.assertTrue(os.path.isfile(path), item)
                if category != "config":  # a config surface lists keys, not one declaration
                    with open(path, encoding="utf-8") as f:
                        self.assertIn(item.get("line"), range(1, f.read().count("\n") + 2), item)
        for category, lines in expected.get("lines", {}).items():
            got = {i.get("name") or i.get("event"): i["line"] for i in result["surfaces"][category]}
            self.assertEqual({name: got.get(name) for name in lines}, lines, f"{category} lines")
        for api_name, kind in expected.get("api_kinds", {}).items():
            self.assertEqual(next(a["kind"] for a in result["surfaces"]["api"] if a["name"] == api_name), kind, api_name)
        for tool, description in expected.get("tool_descriptions", {}).items():
            self.assertEqual(next(t["description"] for t in result["surfaces"]["tools"] if t["name"] == tool), description)
        if "action" in expected:
            action, want = result["surfaces"]["action"], expected["action"]
            self.assertEqual((action["name"], action["runs"], action["certain"]), (want["name"], want["runs"], want["certain"]))
            self.assertEqual(sorted(action["outputs"]), sorted(want["outputs"]))
            self.assertEqual(set(action["inputs"]), set(want["inputs"]))
            for key, fields in want["inputs"].items():
                for field, value in fields.items():
                    self.assertEqual(action["inputs"][key][field], value, f"input {key}.{field}")
        dynamic = {e["path"] for e in result["skipped"]["sample"] if e["reason"] == "dynamic"}
        self.assertEqual(dynamic, set(expected.get("dynamic", [])), "dynamic registrations")
        names = every_name(result)
        for decoy in expected["never"]:
            self.assertNotIn(decoy, names, f"decoy {decoy} reported")
        # The fixtures live inside this repository: its git history must not leak in.
        self.assertFalse(result["history"]["git"])
        self.assertIsNone(result["history"]["commits"])

    def test_every_fixture_has_an_answer_file(self):
        names = sorted(os.listdir(FIXTURES))
        self.assertGreaterEqual(len(names), 8)
        for name in names:
            self.assertTrue(os.path.isfile(os.path.join(FIXTURES, name, "expected.json")), name)


for _name in sorted(os.listdir(FIXTURES)):
    setattr(FixtureTests, "test_fixture_" + _name.replace("-", "_"), lambda self, n=_name: self.check(n))


class TempTree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "project")
        os.mkdir(self.root)

    def write(self, rel, data=""):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path

    def skipped(self, result, reason):
        return {e["path"] for e in result["skipped"]["sample"] if e["reason"] == reason}


class SafetyTests(TempTree):
    def test_secret_files_are_skipped_and_never_opened(self):
        self.write("README.md", "# x\n")
        self.write("app.py", "import os\nKEY = os.environ.get('APP_KEY')\n")
        secrets = [".env", ".env.production", "id_rsa", "id_ed25519.pub", "server.pem", "tls.key", "aws_credentials.json",
                   "config/secrets.yaml", ".npmrc", ".netrc", "store.keystore"]
        for rel in secrets:
            self.write(rel, "LEAKED_TOKEN=hunter2\n-----BEGIN OPENSSH PRIVATE KEY-----\n")
        self.write(".env.example", "APP_KEY=\n")
        opened = []
        real_os_open, real_open = os.open, builtins.open

        def spy_os_open(path, *args, **kwargs):
            opened.append(str(path))
            return real_os_open(path, *args, **kwargs)

        def spy_open(path, *args, **kwargs):
            opened.append(str(path))
            return real_open(path, *args, **kwargs)

        with mock.patch("os.open", spy_os_open), mock.patch("builtins.open", spy_open):
            result = discover.scan(self.root)
        names = {os.path.basename(p) for p in opened}  # folders are opened by name below their parent
        for rel in secrets:
            self.assertNotIn(os.path.join(os.path.realpath(self.root), rel), opened)
            self.assertNotIn(os.path.basename(rel), names)
        self.assertEqual(self.skipped(result, "secret"), set(secrets))
        dump = json.dumps(result)
        self.assertNotIn("hunter2", dump)
        self.assertNotIn("LEAKED_TOKEN", dump)
        self.assertEqual({e["name"] for e in result["surfaces"]["env"]}, {"APP_KEY"})

    def test_symlinks_are_listed_not_followed(self):
        outside = os.path.join(self.tmp.name, "outside")
        os.mkdir(outside)
        with open(os.path.join(outside, "package.json"), "w") as f:
            json.dump({"name": "outside-pkg", "bin": {"outside": "x.js"}}, f)
        with open(os.path.join(outside, "secret.txt"), "w") as f:
            f.write("do not read")
        self.write("README.md", "# x\n")
        self.write("src/main.py", "print('hi')\n")
        os.symlink(self.root, os.path.join(self.root, "src", "loop"))
        os.symlink("..", os.path.join(self.root, "src", "up"))
        os.symlink(outside, os.path.join(self.root, "escape"))
        os.symlink(os.path.join(outside, "package.json"), os.path.join(self.root, "package.json"))
        start = time.monotonic()
        result = discover.scan(self.root)
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual(self.skipped(result, "symlink"), {"src/loop", "src/up", "escape", "package.json"})
        self.assertEqual(result["manifests"], [])
        self.assertEqual(result["entry_points"], [])
        self.assertNotIn("outside-pkg", json.dumps(result))
        self.assertEqual(result["files"], 2)

    def test_max_files_truncates_and_keeps_root_manifests(self):
        for i in range(120):
            self.write(f"src/a{i:03}/mod.py", f"X{i} = {i}\n")
        self.write("zz_last_root_file.txt", "late root file\n")
        self.write("pyproject.toml", '[project]\nname = "capped"\nversion = "1.0"\n[project.scripts]\ncapped = "capped:main"\n')
        self.write("README.md", "# capped\n")
        result = discover.scan(self.root, max_files=50)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["files"], 50)
        self.assertEqual(result["limits"]["max_files"], 50)
        self.assertIn("pyproject.toml", [m["path"] for m in result["manifests"]])
        self.assertEqual({e["name"] for e in result["entry_points"]}, {"capped"})
        self.assertEqual(result["docs"]["readme"], "README.md")
        self.assertEqual(len(self.skipped(result, "cap")), 1)

    def test_default_cap_is_5000(self):
        for i in range(5001):
            self.write(f"d{i // 500}/f{i}.txt", "x")
        result = discover.scan(self.root)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["files"], 5000)

    def test_large_file_is_skipped_unread(self):
        self.write("big.py", "import os\nos.environ['BIG_VAR']\n" + "# padding\n" * 31000)
        self.write("package.json", json.dumps({"name": "big", "bin": {"big": "x.js"}, "pad": "x" * 300000}))
        result = discover.scan(self.root)
        self.assertEqual(self.skipped(result, "too-large"), {"big.py", "package.json"})
        self.assertEqual(result["surfaces"]["env"], [])
        self.assertEqual(result["manifests"], [])
        small = discover.scan(self.root, max_bytes=10 ** 6)
        self.assertEqual(self.skipped(small, "too-large"), set())

    def test_binary_files_are_skipped_and_images_measured(self):
        self.write("data.txt", b"text\x00with a NUL byte")
        self.write("lib.so", b"\x7fELF")
        self.write("archive.zip", b"PK\x03\x04")
        png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 640, 480) + b"\x08\x06\x00\x00\x00"
        gif = b"GIF89a" + struct.pack("<HH", 32, 16) + b"\x00" * 8
        jpeg = (b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
                + b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 300, 200) + b"\x03" + b"\x00" * 9)
        webp = b"RIFF" + struct.pack("<I", 30) + b"WEBPVP8X" + struct.pack("<I", 10) + b"\x00" * 4 + (99).to_bytes(3, "little") + (49).to_bytes(3, "little")
        self.write("shots/hero.png", png)
        self.write("shots/anim.gif", gif)
        self.write("shots/photo.jpg", jpeg)
        self.write("shots/pic.webp", webp)
        self.write("shots/logo.svg", "<svg xmlns='http://www.w3.org/2000/svg'/>")
        result = discover.scan(self.root)
        self.assertEqual(self.skipped(result, "binary"), {"data.txt", "lib.so", "archive.zip"})
        sizes = {i["path"]: (i["width"], i["height"]) for i in result["pictures"]["images"]}
        self.assertEqual(sizes, {"shots/hero.png": (640, 480), "shots/anim.gif": (32, 16), "shots/photo.jpg": (200, 300),
                                 "shots/pic.webp": (100, 50), "shots/logo.svg": (None, None)})
        self.assertEqual(next(i["bytes"] for i in result["pictures"]["images"] if i["path"] == "shots/hero.png"), len(png))

    def test_skip_dirs_and_hidden_entries(self):
        self.write("node_modules/dep/package.json", json.dumps({"name": "dep", "bin": {"dep": "x.js"}}))
        self.write("build/out.py", "import os\nos.environ['BUILD_VAR']\n")
        self.write(".hidden/tool.py", "import os\nos.environ['HIDDEN_VAR']\n")
        self.write(".claude/settings.local.json", '{"token": "x"}')
        self.write(".claude/skills/helper/SKILL.md", "---\nname: helper\ndescription: Helps.\n---\n")
        self.write(".github/workflows/ci.yml", "on: [push]\njobs: {}\n")
        result = discover.scan(self.root)
        self.assertEqual(result["entry_points"], [])
        self.assertEqual(result["surfaces"]["env"], [])
        self.assertIn("node_modules", self.skipped(result, "dir"))
        self.assertIn(".hidden", self.skipped(result, "dir"))
        self.assertEqual([s["name"] for s in result["surfaces"]["skills"]], ["helper"])
        self.assertNotIn(".claude/settings.local.json", json.dumps(result))

    def test_project_code_is_never_run(self):
        marker = os.path.join(self.tmp.name, "RAN")
        payload = f"open({marker!r}, 'w').write('ran')\n"
        self.write("setup.py", "from setuptools import setup\n" + payload + "setup(name='x', entry_points={'console_scripts': ['x = x:main']})\n")
        self.write("conftest.py", payload)
        self.write("x/__init__.py", payload)
        self.write("package.json", json.dumps({"name": "x", "scripts": {"preinstall": f"touch {marker}"}}))
        self.write("Makefile", f"all:\n\ttouch {marker}\n")
        result = discover.scan(self.root)
        self.assertFalse(os.path.exists(marker))
        self.assertEqual({e["name"] for e in result["entry_points"]}, {"x"})

    def test_empty_tree_has_every_key(self):
        result = discover.scan(self.root)
        self.assertEqual(set(result), TOP_KEYS)
        self.assertEqual(set(result["surfaces"]), {"cli", "api", "tools", "commands", "skills", "hooks", "action", "routes",
                                                   "env", "shortcuts", "config"})
        self.assertIsNone(result["surfaces"]["action"])
        self.assertEqual(result["kinds"], [])
        self.assertEqual(result["files"], 0)
        self.assertEqual(result["root"], ".")
        self.assertEqual(set(result["history"]), {"git", "commits", "tags", "last_readme_commit", "since", "since_error",
                                                  "skipped_reason", "changed", "untracked"})

    def test_hostile_files_stay_fast(self):
        pad = 200000
        self.write("a.py", "import argparse, click, flask, mcp\n" + "#\n" * (pad // 2))
        self.write("b.go", 'package main\nimport "net/http"\n' + "//\n" * (pad // 3))
        self.write("c.ts", 'import e from "express";\nimport x from "commander";\n' + "//\n" * (pad // 3))
        self.write("d.qml", "Item {\n" + "Shortcut {\n" * (pad // 11))
        self.write("e.rs", "use clap::Parser;\n#[derive(Parser)]\nstruct A {" + "#[arg(long)]\n" * (pad // 13))
        self.write("f.py", "import argparse\n" + "p.add_argument(\n" * (pad // 16))
        self.write("g.ts", 'import { McpServer } from "@modelcontextprotocol/sdk";\n' + "server.tool(\n" * (pad // 13))
        self.write("h.go", 'package x\nimport "github.com/spf13/cobra"\n' + "x := &cobra.Command{\n" * (pad // 22))
        self.write("compose.yaml", "services:\n" + "  x:\n    ports: [\n" * (pad // 20))
        self.write("SKILL.md", "---\n" + "a: |\n" * (pad // 5))
        start = time.monotonic()
        result = discover.scan(self.root)
        self.assertLess(time.monotonic() - start, 10)
        self.assertEqual(result["files"], 10)

    def test_secret_paths_cover_folders_and_more_names(self):
        self.write("README.md", "# x\n")
        secrets = ["secrets/prod.json", "deploy/secrets/db.yaml", "credentials/service.json", "infra/prod.tfvars",
                   "terraform.tfstate", "terraform.tfstate.backup", "android/release.jks", ".pgpass", ".htpasswd",
                   "vault.kdbx", ".git-credentials"]
        for rel in secrets:
            self.write(rel, "LEAKED_TOKEN=hunter2\n")
        opened = []
        real_os_open = os.open

        def spy(path, *args, **kwargs):  # folders are opened by name below their parent
            opened.append(os.path.basename(path))
            return real_os_open(path, *args, **kwargs)

        with mock.patch("os.open", spy):
            result = discover.scan(self.root)
        never = {part for rel in secrets for part in rel.split("/") if part not in ("deploy", "infra", "android")}
        self.assertEqual(never & set(opened), set())
        self.assertIn("README.md", opened)
        skipped = self.skipped(result, "secret")
        for rel in secrets:
            self.assertTrue(rel in skipped or any(rel.startswith(d + "/") for d in skipped), rel)
        self.assertNotIn("hunter2", json.dumps(result))
        for rel in ("secrets/a.txt", "x/.secrets/b", "keys/prod.tfvars", "terraform.tfstate.1", "a.kdbx"):
            self.assertTrue(discover.is_secret_path(rel), rel)
        for rel in ("src/main.py", "docs/guide.md", ".env.example", "tfvars.md"):
            self.assertFalse(discover.is_secret_path(rel), rel)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes need POSIX")
    def test_image_headers_are_read_bounded_and_only_from_regular_files(self):
        sparse = self.write("shots/huge.jpg", b"\xff\xd8")
        with open(sparse, "r+b") as f:
            f.truncate(1 << 30)  # a gigabyte of zeros, stored as a hole
        start = time.monotonic()
        result = discover.scan(self.root)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(result["pictures"]["images"][0]["width"], None)
        # A segment length below 2 is invalid: it must not seek backward into a frame header.
        bad = self.write("bad.jpg", b"\xff\xd8\xff\xe0\x00\x01" + b"\xff\xc0\x00\x11\x08\x00\x09\x00\x07\x03" + b"\x00" * 20)
        self.assertEqual(discover.image_size(bad), (None, None))
        # A frame header after a large metadata segment is still found.
        big_app = b"\xff\xd8\xff\xe1" + struct.pack(">H", 60000) + b"\x00" * 59998
        good = self.write("good.jpg", big_app + b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 300, 200) + b"\x00" * 12)
        self.assertEqual(discover.image_size(good), (200, 300))
        outside = os.path.join(self.tmp.name, "outside.png")
        with open(outside, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 640, 480) + b"\0" * 5)
        os.symlink(outside, os.path.join(self.root, "link.png"))
        self.assertEqual(discover.image_size(os.path.join(self.root, "link.png")), (None, None))
        os.mkfifo(os.path.join(self.root, "pipe.png"))
        done = []
        reader = threading.Thread(target=lambda: done.append(discover.image_size(os.path.join(self.root, "pipe.png"))),
                                  daemon=True)
        reader.start()
        reader.join(5)
        self.assertEqual(done, [(None, None)], "reading a named pipe as an image blocked")

    def test_walk_and_reads_are_budgeted(self):
        for i in range(200):
            os.mkdir(os.path.join(self.root, f"d{i:03}"))  # folders do not count as files
        self.write("README.md", "# x\n")
        result = discover.scan(self.root, max_files=5)
        self.assertTrue(result["truncated"])
        self.assertIn("cap", result["skipped"]["reasons"])
        for i in range(300):
            os.symlink("README.md", os.path.join(self.root, "d000", f"link{i}"))
        scanner = discover.Scanner(self.root, 5000, 262144)
        scanner.walk()
        self.assertEqual(scanner.skip_reasons["symlink"], 300)
        self.assertEqual(len([e for e in scanner.skipped if e["reason"] == "symlink"]), discover.SAMPLE_LIMIT)
        for i in range(5):
            self.write(f"src/m{i}.py", "import os\nX = os.environ.get('V%d')\n" % i + "#" * 100)
        with mock.patch.object(discover, "TEXT_BUDGET", 300):
            result = discover.scan(self.root)
        self.assertTrue(result["truncated"])
        self.assertLess(len(result["surfaces"]["env"]), 5)

    def test_a_folder_swapped_for_a_symlink_is_not_followed(self):
        self.write("src/a.py", "A = 1\n" + "#\n" * 5000)  # larger than the head the walk keeps
        outside = os.path.join(self.tmp.name, "outside")
        os.mkdir(outside)
        with open(os.path.join(outside, "a.py"), "w") as f:
            f.write("SECRET = 'outside the root'\n" + "#\n" * 5000)
        scanner = discover.Scanner(self.root, 100, 262144)
        scanner.walk()
        os.rename(os.path.join(self.root, "src"), os.path.join(self.root, "src.real"))
        try:
            os.symlink(outside, os.path.join(self.root, "src"), target_is_directory=True)
        except OSError as err:
            self.skipTest(f"symlinks are not available here: {err}")
        self.assertIsNone(scanner.read("src/a.py"))
        self.assertEqual(discover.image_size("src/a.py", scanner.root), (None, None))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes need POSIX")
    def test_read_bytes_refuses_what_is_not_a_regular_file(self):
        # A file can be swapped for a folder or a pipe between the walk and the read.
        self.write("README.md", "# x\n")
        os.mkdir(os.path.join(self.root, "was-a-file"))
        os.mkfifo(os.path.join(self.root, "pipe"))
        scanner = discover.Scanner(self.root, 10, 1000)
        self.assertIsNone(scanner.read_bytes("was-a-file", 100))
        self.assertIsNone(scanner.read_bytes("pipe", 100))
        self.assertEqual(scanner.read_bytes("README.md", 100), b"# x\n")

    def test_performance_on_5000_files(self):
        for i in range(5000):
            if i % 2:
                self.write(f"pkg{i // 250}/m{i}.py", f"import os\n\ndef f{i}(x):\n    return os.environ.get('V{i % 7}')\n")
            else:
                self.write(f"web{i // 250}/m{i}.ts", f"export function f{i}(x: number) {{ return fetch('/x' + x); }}\n")
        start = time.monotonic()
        result = discover.scan(self.root)
        self.assertLess(time.monotonic() - start, 10)
        self.assertEqual(result["files"], 5000)
        self.assertFalse(result["truncated"])


ECOSYSTEMS = {
    "go-cli-lib": {
        "files": {
            "go.mod": "module github.com/acme/gotool\n\ngo 1.22\n",
            "lib.go": "package gotool\n\nfunc Parse(s string) error { return nil }\n\ntype Config struct{}\n\nfunc helper() {}\n",
            "internal/x/x.go": "package x\n\nfunc Hidden() {}\n",
            "cmd/gotool/main.go": (
                'package main\n\nimport (\n\t"os"\n\t"github.com/spf13/cobra"\n)\n\n'
                'var rootCmd = &cobra.Command{Use: "gotool", Short: "A tool"}\n'
                'var serveCmd = &cobra.Command{Use: "serve [addr]", Short: "Serve"}\n'
                'var debugCmd = &cobra.Command{Use: "debug", Hidden: true}\n\n'
                'func main() {\n\trootCmd.PersistentFlags().StringVarP(&cfg, "config", "c", "", "config file")\n'
                '\t// rootCmd.Flags().Bool("legacy", false, "old")\n\t_ = os.Getenv("GOTOOL_HOME")\n\trootCmd.Execute()\n}\n'),
        },
        "kinds": {("terminal", "cli"), ("library", None)}, "entry_points": {"gotool"}, "channels": {"go"},
        "surfaces": {"cli": {"gotool", "serve", "--config"}, "api": {"Parse", "Config"}, "env": {"GOTOOL_HOME"}},
        "never": {"debug", "--legacy", "Hidden", "helper"},
    },
    "python-library": {
        "files": {
            "pyproject.toml": '[project]\nname = "pylib"\nversion = "0.1.0"\nlicense = {text = "MIT"}\n',
            "src/pylib/__init__.py": 'from .core import Thing, make_thing\nfrom ._impl import secret_sauce\n\n__all__ = ["Thing", "make_thing", "DEFAULT", "_hidden"]\n\nDEFAULT = 3\n',
            "src/pylib/core.py": "class Thing:\n    pass\n\n\ndef make_thing():\n    return Thing()\n",
            "src/pylib/_impl.py": "def secret_sauce():\n    return 1\n",
        },
        "kinds": {("library", None)}, "entry_points": set(), "channels": {"pypi"},
        "surfaces": {"api": {"Thing", "make_thing", "DEFAULT"}}, "never": {"secret_sauce", "_hidden"},
    },
    "click-cli": {
        "files": {
            "pyproject.toml": '[project]\nname = "clicky"\nversion = "1.0"\n[project.scripts]\nclicky = "clicky.main:cli"\n',
            "clicky/__init__.py": "",
            "clicky/main.py": (
                "import click\n\n\n@click.group()\ndef cli():\n    pass\n\n\n@cli.command()\n"
                '@click.option("--count", "-c", default=1, help="How many times")\n@click.option("--debug", hidden=True)\n'
                'def greet_user(count):\n    """Greet the user."""\n\n\n@cli.command("sync", help="Sync it")\ndef sync_cmd():\n    pass\n\n\n'
                "@cli.command(hidden=True)\ndef secret():\n    pass\n\n\n@cli.command()\ndef _private():\n    pass\n"),
        },
        "kinds": {("terminal", "cli")}, "entry_points": {"clicky"}, "channels": {"pypi"},
        "surfaces": {"cli": {"greet-user", "sync", "--count"}}, "never": {"--debug", "secret", "_private", "cli"},
    },
    "fastapi-service": {
        "files": {
            "main.py": ('from fastapi import FastAPI\nimport os\n\napp = FastAPI()\n\n@app.get("/items/{item_id}")\ndef read(item_id: int):\n'
                        '    return {}\n\n@app.post("/items")\ndef create():\n    return {}\n\nPORT = int(os.environ["PORT"])\n'),
        },
        "kinds": {("service", "web")}, "entry_points": set(), "channels": set(),
        "surfaces": {"routes": {"GET /items/{item_id}", "POST /items"}, "env": {"PORT"}}, "never": set(),
    },
    "express-service": {
        "files": {
            "package.json": json.dumps({"name": "svc", "private": True, "main": "server.js", "dependencies": {"express": "^4"}}),
            "server.js": ('const express = require("express");\nconst app = express();\napp.get("/", (req, res) => res.send("hi"));\n'
                          'app.post("/api/users", (req, res) => res.json({}));\napp.use("/static", express.static("public"));\n'
                          '// app.delete("/api/users/:id", remove);\napp.get("env");\napp.listen(process.env.PORT || 3000);\n'),
        },
        "kinds": {("service", "web")}, "entry_points": set(), "channels": set(),
        "surfaces": {"routes": {"GET /", "POST /api/users"}, "env": {"PORT"}}, "never": {"/api/users/:id", "/static"},
    },
    "vscode-extension": {
        "files": {
            "package.json": json.dumps({"name": "hello-ext", "publisher": "acme", "version": "0.0.1", "engines": {"vscode": "^1.90.0"},
                                        "main": "./out/extension.js", "contributes": {
                                            "commands": [{"command": "hello.sayHi", "title": "Say Hi"}],
                                            "configuration": {"properties": {"hello.greeting": {"type": "string"}}}}}),
            "src/extension.ts": "export function activate() {}\nexport function deactivate() {}\n",
        },
        "kinds": {("extension", "editor-extension")}, "entry_points": set(), "channels": {"vscode-marketplace"},
        "surfaces": {"commands": {"hello.sayHi"}, "config": {"package.json"}, "api": set()}, "never": set(),
    },
    "pre-commit-and-workflow": {
        "files": {
            ".pre-commit-hooks.yaml": "- id: fix-things\n  name: Fix things\n  entry: fix-things\n  language: python\n",
            ".github/workflows/reuse.yml": "on:\n  workflow_call:\n    inputs:\n      x:\n        type: string\njobs: {}\n",
        },
        "kinds": {("automation", "pre-commit-hook"), ("automation", "reusable-workflow")}, "entry_points": set(), "channels": set(),
        "surfaces": {"hooks": {"pre-commit"}}, "never": set(),
    },
    "browser-extension": {
        "files": {"manifest.json": json.dumps({"manifest_version": 3, "name": "Tab Tamer", "version": "1.0"})},
        "kinds": {("extension", "browser-extension")}, "entry_points": set(), "channels": {"chrome-web-store"},
        "surfaces": {}, "never": set(),
    },
    "hyprland-addon": {
        "files": {
            "pkgbuild/PKGBUILD": ("pkgname=lens\npkgver=0.1.0\narch=('x86_64')\ndepends=('hyprland>=0.56')\nsource=()\n\npackage() {\n"
                                  '  install -Dm755 src/lens "$pkgdir/usr/bin/lens"\n  install -Dm755 build/lens-helper "$pkgdir/usr/bin/lens-helper"\n}\n'),
            "src/lens": ('#!/bin/sh\n# lens: turn lens on or off.\nset -eu\n\ncase "${1:-}" in\n  enable)\n    case "$2" in\n      quiet) ;;\n    esac\n    ;;\n'
                         '  disable | off)\n    echo off\n    ;;\n  # legacy) echo old ;;\n  --version)\n    echo 0.1.0\n    ;;\n  -h | --help | help)\n    echo usage\n    ;;\n'
                         '  *)\n    exit 2\n    ;;\nesac\n'),
            "src/hypr/lens.lua": "local M = {}\n-- hl.dispatch(hl.dsp.old())\nfunction M.setup()\n  hl.dispatch(hl.dsp.window.float({}))\nend\nreturn M\n",
        },
        "kinds": {("terminal", "cli"), ("extension", "compositor-plugin")}, "entry_points": {"lens", "lens-helper"},
        "channels": {"pacman"}, "surfaces": {"cli": {"enable", "disable", "--version", "--help"}}, "never": {"quiet", "legacy", "off"},
    },
    "python-mcp-server": {
        "files": {
            "pyproject.toml": '[project]\nname = "notes-mcp"\nversion = "0.1.0"\n[project.scripts]\nnotes-mcp = "server:main"\n',
            "server.py": ('from mcp.server.fastmcp import FastMCP\n\nmcp = FastMCP("notes")\n\n\n@mcp.tool()\ndef add_note(text: str) -> str:\n'
                          '    """Add a note."""\n    return text\n\n\n@mcp.tool(name="search_notes", description="Find notes")\ndef search(q: str):\n'
                          '    return []\n\n\nfor name in ("a", "b"):\n    mcp.tool(name=name)(lambda: None)\n\n\n# @mcp.tool()\n# def old_tool(): ...\n'),
        },
        "kinds": {("extension", "mcp-server")}, "entry_points": {"notes-mcp"}, "channels": {"pypi"},
        "surfaces": {"tools": {"add_note", "search_notes"}}, "never": {"old_tool", "search"},
    },
}


class EcosystemTests(TempTree):
    """Small projects for the ecosystems the fixtures do not cover."""

    def check(self, name):
        spec = ECOSYSTEMS[name]
        for rel, text in spec["files"].items():
            self.write(rel, text)
        result = discover.scan(self.root)
        self.assertEqual({(k["kind"], k["subkind"]) for k in result["kinds"]}, spec["kinds"])
        self.assertEqual({e["name"] for e in result["entry_points"]}, spec["entry_points"])
        self.assertEqual({c["channel"] for c in result["channels"]}, spec["channels"])
        for category, names in spec["surfaces"].items():
            self.assertEqual(set(item_names(category, result["surfaces"][category])), names, category)
        self.assertFalse(spec["never"] & every_name(result))
        return result


for _name in ECOSYSTEMS:
    setattr(EcosystemTests, "test_" + _name.replace("-", "_"), lambda self, n=_name: self.check(n) and None)


MCP_PY = "from mcp.server.fastmcp import FastMCP\nmcp = FastMCP('x')\n"


class ParserTests(TempTree):
    """Valid code and odd manifests that once stopped or skewed the scan."""

    def scan(self, files, **kwargs):
        for rel, text in files.items():
            self.write(rel, text)
        return discover.scan(self.root, **kwargs)

    def names(self, result, category):
        return sorted(item_names(category, result["surfaces"][category]))

    def test_bare_and_nonliteral_mcp_tool_decorators(self):
        result = self.scan({"server.py": MCP_PY + "TOOL_NAME = 'search'\n\n@mcp.tool\ndef add(a: int) -> int:\n"
                            "    return a\n\n@mcp.tool(name=TOOL_NAME)\ndef run(q: str) -> str:\n    return q\n"})
        self.assertEqual(self.names(result, "tools"), ["add"])
        self.assertEqual([(e["path"], e["line"]) for e in result["skipped"]["sample"] if e["reason"] == "dynamic"],
                         [("server.py", 9)])
        self.assertEqual([(g["area"], g["path"]) for g in discover.gaps(result)], [("tools", "server.py")])

    def test_flask_routes_and_their_methods(self):
        result = self.scan({"app.py": "from flask import Flask\napp = Flask(__name__)\n\n@app.route(\"/methods\")\n"
                            "def a():\n    return ''\n\n@app.route('/x', methods=['POST', 'PUT'])\ndef b():\n"
                            "    return ''\n"})
        self.assertEqual(self.names(result, "routes"), ["GET /methods", "POST /x", "PUT /x"])

    def test_export_list_with_a_binding_named_type(self):
        result = self.scan({"package.json": '{"name": "x", "exports": "./src/index.ts"}',
                            "src/index.ts": "const type = 1;\nexport { type };\nexport { type as kind };\n"
                                            "export { type Foo } from './foo';\n",
                            "src/foo.ts": "export interface Foo {}\n"})
        kinds = {a["name"]: a["kind"] for a in result["surfaces"]["api"]}
        self.assertEqual(kinds, {"type": "const", "kind": "const", "Foo": "type"})

    def test_malformed_manifests_are_reported_and_the_scan_goes_on(self):
        result = self.scan({"pyproject.toml": '[project]\nname = "x"\nscripts = ["hello"]\n',
                            "tools/pyproject.toml": 'project = "x"\n',
                            "crate/Cargo.toml": 'package = "x"\ndependencies = ["serde"]\n',
                            "web/package.json": '{"name": "w", "os": [["linux"]], "bin": {"w": "cli.js"}}',
                            "web/cli.js": "#!/usr/bin/env node\n",
                            "lib/package.json": '{"name": "healthy", "bin": {"healthy": "cli.js"}}',
                            "lib/cli.js": "#!/usr/bin/env node\n"})
        self.assertEqual({e["name"] for e in result["entry_points"]}, {"w", "healthy"})
        self.assertIn("x", {m["name"] for m in result["manifests"]})
        malformed = {e["path"] for e in result["skipped"]["sample"] if e["reason"] == "malformed"}
        self.assertEqual(malformed, {"pyproject.toml", "crate/Cargo.toml", "web/package.json"})
        self.assertEqual({g["path"] for g in discover.gaps(result) if g["area"] == "manifests"}, malformed)

    def test_standalone_cli_beside_a_tooling_only_pyproject(self):
        result = self.scan({"pyproject.toml": "[tool.ruff]\nline-length = 100\n",
                            "main.py": "import argparse\n\n\ndef main():\n    p = argparse.ArgumentParser()\n"
                                       "    p.add_argument('--name')\n    p.parse_args()\n\n\n"
                                       "if __name__ == '__main__':\n    main()\n"})
        self.assertEqual({e["name"] for e in result["entry_points"]}, {"main"})
        self.assertEqual(self.names(result, "cli"), ["--name"])

    def test_exports_win_over_web_tooling(self):
        result = self.scan({"package.json": '{"name": "lib", "exports": "./src/index.ts", '
                                            '"devDependencies": {"next": "14"}}',
                            "src/index.ts": "export function hello() {}\n"})
        self.assertIn(("library", None), {(k["kind"], k["subkind"]) for k in result["kinds"]})
        self.assertEqual(self.names(result, "api"), ["hello"])

    def test_inventory_paths_stay_posix_under_windows_path_rules(self):
        files = {"package.json": '{"name": "x", "exports": "./src/index.ts", "bin": {"x": "bin/x.js"}}',
                 "src/index.ts": "export function one() {}\nexport * from './more';\n",
                 "src/more.ts": "export const two = 2;\n", "bin/x.js": "#!/usr/bin/env node\n",
                 "crate/Cargo.toml": '[package]\nname = "c"\n', "crate/src/main.rs": "fn main() {}\n",
                 "crate/src/lib.rs": "pub fn three() {}\n"}
        for rel, text in files.items():
            self.write(rel, text)
        s = discover.Scanner(self.root, 100, 100000)
        s.walk()
        for rel in list(s.sizes):
            s.read(rel)  # cached, so the steps below never touch the file system
        with mock.patch.object(os, "path", ntpath):
            for step in discover.ECOSYSTEMS:
                step(s)
        self.assertEqual(sorted(a["name"] for a in s.surfaces["api"]), ["one", "three", "two"])
        self.assertIn("bin/x.js", s.declared)
        self.assertEqual({e["name"] for e in s.entry_points}, {"x", "c"})

    def test_gaps_name_what_discovery_could_not_read(self):
        big = MCP_PY + "\n@mcp.tool()\ndef later() -> None:\n    pass\n" + "# padding\n" * 30000
        result = self.scan({"server.py": MCP_PY + "\n@mcp.tool()\ndef first() -> None:\n    pass\n",
                            "more_tools.py": big, "package-lock.json": "{}" + " " * 300000})
        self.assertEqual([(g["area"], g["path"]) for g in discover.gaps(result)], [("sources", "more_tools.py")])
        truncated = discover.scan(self.root, max_files=1)
        self.assertEqual({g["area"] for g in discover.gaps(truncated)}, {"sources", "manifests"})

    def test_many_surfaces_stay_linear(self):
        for i in range(10):
            self.write(f"m{i}.py", "import os\n" + "".join(f"os.environ['V{i}_{k}']\n" for k in range(3000)))
        start = time.monotonic()
        result = discover.scan(self.root)
        self.assertLess(time.monotonic() - start, 10)
        self.assertEqual(len(result["surfaces"]["env"]), 30000)

    def test_skill_and_command_surfaces_carry_declaration_lines(self):
        result = self.scan({".claude-plugin/plugin.json": '{"name": "p"}',
                            "skills/helper/SKILL.md": "---\nname: helper\ndescription: Helps.\n---\n# Helper\n",
                            "commands/go.md": "---\ndescription: Go.\n---\nGo now.\n",
                            "package.json": '{"name": "v", "engines": {"vscode": "^1.80.0"}, "contributes": '
                                            '{"commands": [\n  {"command": "v.run", "title": "Run"}\n]}}'})
        lines = {(c, i.get("name")): i.get("line") for c in ("skills", "commands") for i in result["surfaces"][c]}
        self.assertEqual(lines, {("skills", "helper"): 2, ("commands", "go"): 1, ("commands", "v.run"): 2})


    def test_tools_registered_through_a_server_made_in_another_module(self):
        result = self.scan({"pkg/app.py": MCP_PY + "\n@mcp.tool()\ndef first() -> None:\n    pass\n",
                            "pkg/more.py": "from pkg.app import mcp\n\n\n@mcp.tool()\ndef later() -> None:\n    pass\n",
                            "pkg/other.py": "from somewhere import thing\n\n\n@thing.tool()\ndef maybe() -> None:\n    pass\n",
                            "web/server.ts": "import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';\n"
                                             "export const server = new McpServer({name: 'x', version: '1'});\n",
                            "web/tools.ts": "import { server } from './server';\nserver.tool('lookup', 'Looks', async () => ({}));\n"})
        self.assertEqual(self.names(result, "tools"), ["first", "later", "lookup"])
        # A registration through an object no MCP module made is a gap, not a silent absence.
        self.assertEqual([(g["area"], g["path"]) for g in discover.gaps(result)], [("tools", "pkg/other.py")])

    def test_registrations_past_the_limit_are_a_gap(self):
        tools = "".join("@mcp.tool()\ndef t%d() -> None:\n    pass\n\n" % k for k in range(6))
        with mock.patch.object(discover, "CALL_LIMIT", 5):
            result = self.scan({"server.py": MCP_PY + tools})
        self.assertEqual(len(result["surfaces"]["tools"]), 5)
        self.assertEqual([(g["area"], g["path"]) for g in discover.gaps(result)], [("tools", "server.py")])

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "permissions do not stop this user reading")
    def test_sources_that_cannot_be_read_are_a_gap(self):
        self.write("server.py", MCP_PY)
        path = self.write("more.py", MCP_PY)
        os.chmod(path, 0)
        self.addCleanup(os.chmod, path, 0o644)
        result = discover.scan(self.root)
        self.assertIn("more.py", self.skipped(result, "unreadable"))
        self.assertEqual([(g["area"], g["path"]) for g in discover.gaps(result)], [("sources", "more.py")])

    def test_manifests_that_do_not_parse_are_a_gap(self):
        result = self.scan({"pyproject.toml": "[project\nname = \n", "crate/Cargo.toml": "[package\n",
                            "web/package.json": "{name: x}", "setup.cfg": "[metadata\nname = x\n",
                            "compose.yaml": "- just\n- a list\n", "skills/s/SKILL.md": "---\nname: [s\n---\n",
                            ".claude-plugin/plugin.json": "[1]", "deno.jsonc": "{// comment\n}",
                            "action.yml": "# only a comment\n"})
        self.assertEqual({g["path"] for g in discover.gaps(result) if g["area"] == "manifests"},
                         {"pyproject.toml", "crate/Cargo.toml", "web/package.json", "setup.cfg", "compose.yaml",
                          "skills/s/SKILL.md", ".claude-plugin/plugin.json"})

    def test_installed_copies_of_this_skill_are_left_out(self):
        own = "---\nname: readme-workshop\ndescription: Writes READMEs.\n---\n# Workshop\n"
        files = {"pyproject.toml": '[project]\nname = "tool"\n', "tool/__init__.py": "",
                 ".claude/skills/readme-workshop/SKILL.md": own, ".agents/skills/readme-workshop/SKILL.md": own,
                 "skills/readme-workshop/SKILL.md": own,
                 "skills/readme-workshop/scripts/discover.py": "import argparse\n",
                 "skills/helper/SKILL.md": "---\nname: helper\ndescription: Helps.\n---\n# Helper\n"}
        result = self.scan(files)
        self.assertEqual(self.names(result, "skills"), ["helper"])
        self.assertEqual(self.skipped(result, "installed-skill"),
                         {".claude/skills/readme-workshop", ".agents/skills/readme-workshop", "skills/readme-workshop"})
        self.assertFalse(any(f.startswith("skills/readme-workshop") for f in result["docs"]["docs_dir"]))
        # The project that ships this skill keeps it; a skill only named like it elsewhere is its own.
        self.write(".claude-plugin/plugin.json", '{"name": "readme-workshop"}')
        result = discover.scan(self.root)
        self.assertEqual(self.names(result, "skills"), ["helper", "readme-workshop"])
        self.assertEqual(self.skipped(result, "installed-skill"),
                         {".claude/skills/readme-workshop", ".agents/skills/readme-workshop"})

    def test_sensitive_action_input_defaults_are_not_reported(self):
        result = self.scan({"action.yml": "name: x\ndescription: d\ninputs:\n  password:\n    default: dummy-pw\n"
                                          "  API_Key:\n    default: k-123\n  token:\n    default: ${{ github.token }}\n"
                                          "  path:\n    default: docs\nruns:\n  using: node20\n  main: x.js\n"})
        inputs = result["surfaces"]["action"]["inputs"]
        self.assertEqual({k: v["default"] for k, v in inputs.items()},
                         {"password": "(set, hidden)", "API_Key": "(set, hidden)", "token": "(set, hidden)",
                          "path": "docs"})
        self.assertNotIn("dummy-pw", json.dumps(result))


@unittest.skipUnless(HAS_GIT, "git is not installed")
class SinceTests(TempTree):
    def test_since_keeps_kinds_from_the_whole_project(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t",
                   GIT_AUTHOR_EMAIL="t@example.org", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.org")
        self.write("app.py", "from flask import Flask\napp = Flask(__name__)\n\n@app.route('/')\ndef home():\n"
                             "    return ''\n")
        self.write("README.md", "# x\n")
        for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "x")):
            subprocess.run(["git", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", *args],
                           cwd=self.root, env=env, check=True, capture_output=True)
        full, since = discover.scan(self.root), discover.scan(self.root, since="HEAD")
        kinds = lambda r: {(k["kind"], k["subkind"]) for k in r["kinds"]}  # noqa: E731
        self.assertIn(("service", "web"), kinds(full))
        self.assertEqual(kinds(since), kinds(full))
        self.assertEqual(full["surfaces"]["routes"][0]["route"], "/")
        self.assertEqual(since["surfaces"]["routes"], [])


@unittest.skipUnless(HAS_GIT, "git is not installed")
class GitTests(TempTree):
    def git(self, *args, cwd=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.org",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.org")
        return subprocess.run(["git", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                              cwd=cwd or self.root, env=env, check=True, capture_output=True, text=True).stdout

    def make_repo(self):
        self.git("init", "-q")
        self.write("README.md", "# repo\n")
        self.write("a.py", "import os\nA = os.environ.get('A_VAR')\n")
        self.write("b.py", "import os\nB = os.environ.get('B_VAR')\n")
        self.write("old.py", "import os\nC = os.environ.get('C_VAR')\nprint('a file long enough to be found as a rename')\n")
        self.write("gone.py", "print('bye')\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "first")
        self.git("tag", "v1.0")

    def test_history_and_since(self):
        self.make_repo()
        self.git("mv", "old.py", "new.py")
        self.git("rm", "-q", "gone.py")
        self.write("a.py", "import os\nA = os.environ.get('A_VAR')\nA2 = os.environ.get('A2_VAR')\n")
        self.git("commit", "-q", "-am", "second")
        self.write("untracked.py", "import os\nU = os.environ.get('U_VAR')\n")
        self.write("b.py", "import os\nB = os.environ.get('B_VAR')\nB2 = os.environ.get('B2_VAR')\n")  # not committed
        result = discover.scan(self.root, since="v1.0")
        h = result["history"]
        self.assertTrue(h["git"])
        self.assertEqual(h["commits"], 2)
        self.assertEqual(h["tags"], ["v1.0"])
        self.assertEqual(h["last_readme_commit"], self.git("rev-parse", "v1.0").strip())
        self.assertEqual(h["since"], "v1.0")
        self.assertIsNone(h["since_error"])
        changed = {(c["path"], c["status"]) for c in h["changed"]}
        self.assertEqual(changed, {("new.py", "R"), ("gone.py", "D"), ("a.py", "M")})
        self.assertEqual(next(c["from"] for c in h["changed"] if c["status"] == "R"), "old.py")
        self.assertEqual(h["untracked"], ["untracked.py"])
        # Surfaces come only from the committed changes and untracked files; the working tree is never diffed.
        self.assertEqual({e["name"] for e in result["surfaces"]["env"]}, {"A_VAR", "A2_VAR", "C_VAR", "U_VAR"})

    def test_tags_made_together_list_the_highest_version_first(self):
        self.make_repo()
        for tag in ("v1.10", "v1.9"):
            self.git("tag", tag)
        self.assertEqual(discover.scan(self.root)["history"]["tags"], ["v1.10", "v1.9", "v1.0"])

    def test_git_output_is_capped(self):
        self.make_repo()
        for i in range(50):
            self.write(f"untracked{i:02}.py", "x = 1\n")
        with mock.patch.object(discover, "GIT_OUTPUT_LIMIT", 100):
            result = discover.scan(self.root, since="v1.0")
        self.assertEqual(result["history"]["since_error"], "git could not list the changes; this is a full scan")
        self.assertEqual(result["history"]["commits"], 1)

    @unittest.skipIf(os.name == "nt", "POSIX shell scripts and symlinks build these hostile repositories; the same protections are tested on Linux and macOS")
    def test_hostile_repository_config_runs_nothing(self):
        self.make_repo()
        self.write(".gitattributes", "* filter=evil\n")
        self.git("add", ".gitattributes")
        self.git("commit", "-q", "-m", "attributes")
        marker = os.path.join(self.tmp.name, "RAN")
        script = os.path.join(self.tmp.name, "evil.sh")
        with open(script, "w") as f:
            f.write(f"#!/bin/sh\necho \"$0 $*\" >> {marker}\ncat\n")
        os.chmod(script, 0o755)
        with open(os.path.join(self.root, ".git", "config"), "a") as f:
            f.write(f"[core]\n\tfsmonitor = {script}\n\tpager = {script}\n\thooksPath = {self.tmp.name}\n"
                    f"[filter \"evil\"]\n\tclean = {script}\n\tsmudge = {script}\n"
                    f"[log]\n\tshowSignature = true\n[gpg]\n\tprogram = {script}\n[diff]\n\texternal = {script}\n")
        self.write("a.py", "import os\nA = os.environ.get('A_VAR')\n# changed, not committed\n")
        os.utime(os.path.join(self.root, "a.py"), (946684800, 946684800))
        result = discover.scan(self.root, since="HEAD~1")
        self.assertFalse(os.path.exists(marker), "git ran a program from the repository's config")
        self.assertIsNone(result["history"]["since_error"])
        self.assertEqual({c["path"] for c in result["history"]["changed"]}, {".gitattributes"})

    def hostile_git_dir(self, git_dir):
        """Make git_dir a partial clone whose missing objects would be fetched by programs it names.

        Returns the marker file each of those programs would write."""
        tree = self.git("rev-parse", "HEAD^{tree}").strip()
        os.remove(os.path.join(git_dir, "objects", tree[:2], tree[2:]))  # git log -- README.md needs it
        marker = os.path.join(self.tmp.name, "RAN")
        script = os.path.join(self.tmp.name, "evil.sh")
        with open(script, "w") as f:
            f.write(f"#!/bin/sh\necho \"$0 $*\" >> {marker}\nexit 1\n")
        os.chmod(script, 0o755)
        with open(os.path.join(git_dir, "config"), "a") as f:
            f.write(f"[core]\n\trepositoryformatversion = 1\n\tsshCommand = {script}\n\taskPass = {script}\n"
                    f"\talternateRefsCommand = {script}\n\teditor = {script}\n"
                    f"[extensions]\n\tpartialClone = origin\n"
                    f"[remote \"origin\"]\n\turl = {self.tmp.name}\n\tpromisor = true\n\tuploadpack = {script}\n"
                    f"[remote \"other\"]\n\turl = ssh://example.invalid/x\n\tpromisor = true\n"
                    f"[remote \"web\"]\n\turl = https://example.invalid/x\n\tpromisor = true\n"
                    f"[credential]\n\thelper = !{script}\n[uploadpack]\n\tpackObjectsHook = {script}\n"
                    f"[protocol \"file\"]\n\tallow = always\n[protocol \"ssh\"]\n\tallow = always\n")
        return marker

    @unittest.skipIf(os.name == "nt", "POSIX shell scripts and symlinks build these hostile repositories; the same protections are tested on Linux and macOS")
    def test_lazy_fetch_and_transport_programs_never_run(self):
        self.make_repo()
        marker = self.hostile_git_dir(os.path.join(self.root, ".git"))
        objects = lambda: sorted(os.path.join(d, f) for d, _, fs in os.walk(os.path.join(self.root, ".git", "objects"))
                                 for f in fs)  # noqa: E731
        before = objects()
        result = discover.scan(self.root, since="v1.0")
        self.assertFalse(os.path.exists(marker), "git ran a program named by the repository's config")
        self.assertEqual(objects(), before, "discovery wrote to the object store")
        h = result["history"]
        # A partial clone is not read at all: git would fetch its missing objects.
        self.assertFalse(h["git"])
        self.assertIn("partial clone", h["skipped_reason"])
        self.assertEqual({e["name"] for e in result["surfaces"]["env"]}, {"A_VAR", "B_VAR", "C_VAR"})

    def test_partial_clones_are_not_read(self):
        for k, (name, make) in enumerate((
                ("extensions.partialClone", lambda: self.append_config("[extensions]\n\tpartialClone = origin\n")),
                ("remote promisor", lambda: self.append_config('[remote "o"]\n\turl = x\n\tpromisor\n')),
                ("old-style section", lambda: self.append_config("[remote.o]\n\tpromisor = yes\n")),
                ("promisor pack", lambda: self.write(".git/objects/pack/pack-1.promisor", "")))):
            with self.subTest(case=name):
                self.root = os.path.join(self.tmp.name, "case%d" % k)
                os.mkdir(self.root)
                self.make_repo()
                make()
                calls = []
                real_popen = subprocess.Popen
                with mock.patch.object(discover.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd) or real_popen(cmd, **kw)):
                    result = discover.scan(self.root, since="v1.0")
                self.assertEqual(calls, [])
                self.assertIn("partial clone", result["history"]["skipped_reason"])

    def append_config(self, text):
        with open(os.path.join(self.root, ".git", "config"), "a") as f:
            f.write(text)

    @unittest.skipIf(os.name == "nt", "POSIX shell scripts and symlinks build these hostile repositories; the same protections are tested on Linux and macOS")
    def test_git_dir_must_be_a_real_folder(self):
        # A .git symlink or "gitdir:" file can lead git to a repository outside the root.
        self.make_repo()
        marker = self.hostile_git_dir(os.path.join(self.root, ".git"))
        hostile = os.path.join(self.tmp.name, "elsewhere.git")
        os.rename(os.path.join(self.root, ".git"), hostile)
        entry = os.path.join(self.root, ".git")
        real_popen = subprocess.Popen
        for layout in ("symlink", "gitdir file"):
            with self.subTest(layout=layout):
                if layout == "symlink":
                    os.symlink(hostile, entry)
                else:
                    with open(entry, "w") as f:
                        f.write(f"gitdir: {hostile}\n")
                calls = []

                def spy(cmd, **kwargs):
                    calls.append(cmd)
                    return real_popen(cmd, **kwargs)

                with mock.patch.object(discover.subprocess, "Popen", spy):
                    result = discover.scan(self.root, since="v1.0")
                os.remove(entry)
                self.assertFalse(os.path.exists(marker), "git ran a program named by the repository's config")
                self.assertEqual(calls, [])
                self.assertFalse(result["history"]["git"])
                self.assertIsNotNone(result["history"]["since_error"])
                self.assertIn(".git is a", result["history"]["skipped_reason"])
                self.assertEqual({e["name"] for e in result["surfaces"]["env"]}, {"A_VAR", "B_VAR", "C_VAR"})

    def test_history_is_skipped_when_git_data_lies_outside(self):
        self.make_repo()
        git_dir = os.path.join(self.root, ".git")
        outside = os.path.join(self.tmp.name, "outside.cfg")
        with open(outside, "w") as f:
            f.write("[core]\n\tabbrev = 12\n")
        inside = os.path.join(self.root, "inside.cfg")
        with open(inside, "w") as f:
            f.write(f"[include]\n\tpath = {outside}\n")
        with open(os.path.join(git_dir, "config")) as f:
            config = f.read()
        def append(rel, text):
            with open(os.path.join(git_dir, *rel.split("/")), "a") as f:
                f.write(text)

        def symlinked_config():
            os.rename(os.path.join(git_dir, "config"), outside + ".real")
            os.symlink(outside + ".real", os.path.join(git_dir, "config"))

        cases = {
            "commondir": lambda: append("commondir", "../elsewhere\n"),
            "alternates": lambda: append("objects/info/alternates", self.tmp.name + "\n"),
            "include outside": lambda: append("config", f"[include]\n\tpath = {outside}\n"),
            "includeIf home": lambda: append("config", '[includeIf "gitdir:/"]\n\tpath = ~/.gitconfig\n'),
            "include in turn": lambda: append("config", "[include]\n\tpath = ../inside.cfg\n"),
            "symlinked config": symlinked_config,
        }
        for name, make in cases.items():
            with self.subTest(case=name):
                make()
                result = discover.scan(self.root, since="v1.0")
                self.assertFalse(result["history"]["git"])
                self.assertTrue(result["history"]["skipped_reason"])
                self.assertIn("history was not read", result["history"]["since_error"])
                for extra in ("commondir", "objects/info/alternates", "config"):
                    path = os.path.join(git_dir, *extra.split("/"))
                    if os.path.lexists(path):
                        os.remove(path)
                with open(os.path.join(git_dir, "config"), "w") as f:
                    f.write(config)
        with open(os.path.join(git_dir, "config"), "a") as f:
            f.write('[include]\n\tpath = "../inside.cfg" ; but this one only points inside\n')
        with open(inside, "w") as f:
            f.write("[core]\n\tabbrev = 12\n")
        result = discover.scan(self.root)
        self.assertTrue(result["history"]["git"])
        self.assertIsNone(result["history"]["skipped_reason"])

    @unittest.skipIf(os.name == "nt", "POSIX shell scripts and symlinks build these hostile repositories; the same protections are tested on Linux and macOS")
    def test_history_is_skipped_for_links_deep_in_git_data(self):
        self.make_repo()
        git_dir = os.path.join(self.root, ".git")
        tree = self.git("rev-parse", "HEAD^{tree}").strip()
        loose = os.path.join(git_dir, "objects", tree[:2], tree[2:])
        moved = os.path.join(self.tmp.name, "object")
        os.rename(loose, moved)
        try:
            os.symlink(moved, loose)
        except OSError as err:
            self.skipTest(f"symlinks are not available here: {err}")
        result = discover.scan(self.root, since="v1.0")
        self.assertFalse(result["history"]["git"])
        self.assertEqual(result["history"]["skipped_reason"], f".git/objects/{tree[:2]}/{tree[2:]} is a symlink")
        os.remove(loose)
        os.rename(moved, loose)
        # Past its entry budget, .git is not checked further, and not read.
        with mock.patch.object(discover, "GIT_ENTRY_LIMIT", 5):
            result = discover.scan(self.root)
        self.assertIn("too many to check", result["history"]["skipped_reason"])
        with mock.patch.object(discover, "GIT_DEADLINE", 0):
            result = discover.scan(self.root)
        self.assertIn("took too long", result["history"]["skipped_reason"])
        self.assertTrue(discover.scan(self.root)["history"]["git"])

    def test_includes_are_read_as_git_reads_them(self):
        self.make_repo()
        outside = os.path.join(self.tmp.name, "outside.cfg")
        with open(outside, "w") as f:
            f.write("[core]\n\tabbrev = 12\n")
        with open(os.path.join(self.root, ".git", "config")) as f:
            config = f.read()
        cases = {
            # A value continued on the next line by a final backslash.
            "continued": f"[include]\n\tpath = \\\n{outside}\n",
            "quoted in parts": f'[include]\n\tpath = "{outside[:5]}"{outside[5:]}\n',
            "key in capitals, after the header": f"[Include] PATH = {outside}\n",
            "includeIf": f'[includeIf "onbranch:main"]\n\tpath = {outside}\n',
            "unparseable": "[core\n\tbare = false\n",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                with open(os.path.join(self.root, ".git", "config"), "w") as f:
                    f.write(config + text)
                result = discover.scan(self.root)
                self.assertFalse(result["history"]["git"])
                self.assertTrue(result["history"]["skipped_reason"])
        # Each file is read once, however often it is included; past the byte budget, history is skipped.
        self.write("a.cfg", "[include]\n\tpath = b.cfg\n\tpath = b.cfg\n")
        self.write("b.cfg", "[core]\n\tabbrev = 12\n")
        with open(os.path.join(self.root, ".git", "config"), "w") as f:
            f.write(config + "[include]\n\tpath = ../a.cfg\n\tpath = ../a.cfg\n\tpath = ../missing.cfg\n")
        with OpenCount() as count:
            self.assertTrue(discover.scan(self.root)["history"]["git"])
        # The walk's look at each file, then one read each for the check.
        self.assertEqual((count.names.count("a.cfg"), count.names.count("b.cfg")), (2, 2))
        with mock.patch.object(discover, "GIT_CONFIG_LIMIT", len(config) + 10):
            self.assertIn("too large", discover.scan(self.root)["history"]["skipped_reason"])
        # Includes that loop end the check too (git itself then refuses the config).
        self.write("b.cfg", "[include]\n\tpath = a.cfg\n")
        self.assertIsNone(discover.scan(self.root)["history"]["skipped_reason"])

    def test_the_repository_cannot_choose_the_order_of_changes(self):
        self.make_repo()
        self.write("a.py", "import os\nA = os.environ.get('A_VAR')\n# more\n")
        self.write("b.py", "import os\nB = os.environ.get('B_VAR')\n# more\n")
        self.git("commit", "-q", "-am", "second")
        self.write(".git/order.txt", "b.py\na.py\n")
        with open(os.path.join(self.root, ".git", "config"), "a") as f:
            f.write("[diff]\n\torderFile = .git/order.txt\n")
        self.assertEqual(self.git("-c", "core.hooksPath=/dev/null", "diff", "--name-only", "v1.0", "HEAD").split(),
                         ["b.py", "a.py"])
        result = discover.scan(self.root, since="v1.0")
        self.assertEqual([c["path"] for c in result["history"]["changed"]], ["a.py", "b.py"])

    def test_history_is_skipped_without_a_temporary_folder(self):
        self.make_repo()
        with mock.patch.object(discover.tempfile, "TemporaryDirectory",
                               side_effect=FileNotFoundError(2, "No usable temporary directory found")):
            result = discover.scan(self.root, since="v1.0")
        h = result["history"]
        self.assertFalse(h["git"])
        self.assertIn("no temporary folder", h["skipped_reason"])
        self.assertIn("history was not read", h["since_error"])
        self.assertEqual({e["name"] for e in result["surfaces"]["env"]}, {"A_VAR", "B_VAR", "C_VAR"})

    def test_git_comes_from_outside_the_working_folder_too(self):
        # A checkout with a tooling bin/ above the scanned package, and a trusted folder linking into the project.
        self.make_repo()
        marker = os.path.join(self.tmp.name, "RAN")
        tools = os.path.join(self.tmp.name, "checkout", "bin")
        os.makedirs(tools)
        fake = os.path.join(tools, "git")
        with open(fake, "w") as f:
            f.write(f"#!/bin/sh\ntouch {marker}\n")
        os.chmod(fake, 0o755)
        linked = os.path.join(self.tmp.name, "trusted")
        os.mkdir(linked)
        try:
            os.symlink(self.write("tools/git", f"#!/bin/sh\ntouch {marker}\n"), os.path.join(linked, "git"))
        except OSError as err:
            self.skipTest(f"symlinks are not available here: {err}")
        os.chmod(os.path.join(self.root, "tools", "git"), 0o755)
        here = os.getcwd()
        os.chdir(os.path.dirname(tools))
        self.addCleanup(os.chdir, here)
        for path in (tools, linked):
            with self.subTest(path=os.path.basename(path)), \
                    mock.patch.dict(os.environ, {"PATH": os.pathsep.join([path, os.environ.get("PATH", "")])}):
                result = discover.scan(self.root)
                self.assertFalse(os.path.exists(marker), "a git program from the checkout or the project ran")
                self.assertTrue(result["history"]["git"])
        git = discover.find_git([linked, os.path.dirname(shutil.which("git"))], os.path.realpath(self.root))
        self.assertEqual(git, os.path.realpath(shutil.which("git")))

    def test_git_comes_from_outside_the_project(self):
        # A "git" in the project or the working folder must not be the one that runs.
        self.make_repo()
        marker = os.path.join(self.tmp.name, "RAN")
        fake = self.write("bin/git", f"#!/bin/sh\ntouch {marker}\n")
        os.chmod(fake, 0o755)
        here = os.getcwd()
        os.chdir(os.path.join(self.root, "bin"))
        self.addCleanup(os.chdir, here)
        path = os.pathsep.join([os.path.join(self.root, "bin"), "", ".", os.environ.get("PATH", "")])
        with mock.patch.dict(os.environ, {"PATH": path}):
            result = discover.scan(self.root)
            self.assertFalse(os.path.exists(marker), "a git program from the project ran")
            self.assertTrue(result["history"]["git"])
            with mock.patch.dict(os.environ, {"PATH": os.path.join(self.root, "bin")}):
                result = discover.scan(self.root, since="HEAD")
        self.assertFalse(os.path.exists(marker))
        self.assertFalse(result["history"]["git"])
        self.assertIn("no git program", result["history"]["skipped_reason"])

    def test_history_follows_the_readme_the_scan_found(self):
        self.git("init", "-q")
        self.write("README.rst", "Title\n=====\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "first")
        result = discover.scan(self.root)
        self.assertEqual(result["docs"]["readme"], "README.rst")
        self.assertEqual(result["history"]["last_readme_commit"], self.git("rev-parse", "HEAD").strip())

    def test_unresolvable_ref_falls_back_to_a_full_scan(self):
        self.make_repo()
        for ref in ("no-such-ref", "--output=/tmp/x"):
            result = discover.scan(self.root, since=ref)
            self.assertIsNotNone(result["history"]["since_error"], ref)
            self.assertIsNone(result["history"]["since"])
            self.assertEqual(result["history"]["changed"], [])
            self.assertEqual({e["name"] for e in result["surfaces"]["env"]}, {"A_VAR", "B_VAR", "C_VAR"})

    def test_since_without_git(self):
        self.write("a.py", "x = 1\n")
        result = discover.scan(self.root, since="HEAD")
        self.assertFalse(result["history"]["git"])
        self.assertIsNotNone(result["history"]["since_error"])

    def test_outer_repository_is_not_used(self):
        self.make_repo()
        inner = os.path.join(self.root, "sub")
        os.makedirs(os.path.join(inner, ".git"))  # not a repository: git would walk up without a ceiling
        with open(os.path.join(inner, "x.py"), "w") as f:
            f.write("x = 1\n")
        result = discover.scan(inner)
        self.assertFalse(result["history"]["git"])
        self.assertIsNone(result["history"]["commits"])
        self.assertEqual(result["history"]["tags"], [])

    def test_git_runs_with_ceiling_locks_off_and_timeout(self):
        self.make_repo()
        calls = []
        real = subprocess.Popen

        def spy(cmd, **kwargs):
            calls.append((cmd, kwargs))
            self.assertEqual(os.listdir(kwargs["env"]["HOME"]), [])
            return real(cmd, **kwargs)

        with mock.patch.object(discover.subprocess, "Popen", spy):
            discover.scan(self.root, since="v1.0")
        self.assertTrue(calls)
        self.assertEqual(discover.GIT_TIMEOUT, 10)
        allowed = {"rev-list", "for-each-ref", "log", "rev-parse", "diff", "ls-files"}
        for cmd, kwargs in calls:
            self.assertTrue(os.path.isabs(cmd[0]) and os.path.basename(cmd[0]) in ("git", "git.exe"), cmd[0])
            self.assertEqual(cmd[cmd.index("-C") + 1], os.path.realpath(self.root))
            self.assertIn(cmd[cmd.index("-C") + 2], allowed)
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual(kwargs["env"]["GIT_DIR"], os.path.join(os.path.realpath(self.root), ".git"))
            self.assertNotEqual(kwargs["env"]["HOME"], os.path.expanduser("~"))
            self.assertEqual(kwargs["env"]["GIT_CEILING_DIRECTORIES"], os.path.dirname(os.path.realpath(self.root)))
            self.assertEqual(kwargs["env"]["GIT_OPTIONAL_LOCKS"], "0")
            self.assertEqual(kwargs["env"]["GIT_NO_LAZY_FETCH"], "1")
            self.assertEqual(kwargs["env"]["GIT_CONFIG_GLOBAL"], os.devnull)
            self.assertEqual(kwargs["env"]["GIT_CONFIG_NOSYSTEM"], "1")
            self.assertIn("--no-pager", cmd)
            self.assertIn("protocol.allow=never", cmd)
            self.assertIn("diff.orderFile=" + os.devnull, cmd)
            # An empty list allows no transport at all (the name "none" would allow one called none).
            self.assertEqual(kwargs["env"]["GIT_ALLOW_PROTOCOL"], "")

    def test_fixture_inside_this_repository_has_no_history(self):
        result = discover.scan(os.path.join(FIXTURES, "python-cli"), since="HEAD")
        self.assertFalse(result["history"]["git"])
        self.assertIsNotNone(result["history"]["since_error"])
        self.assertEqual(result["history"]["changed"], [])


class OpenCount:
    """The names of the files os.open opens, by path or below a folder descriptor."""

    def __enter__(self):
        self.names, real = [], os.open

        def counting(path, *args, **kw):
            self.names.append(os.path.basename(str(path)))
            return real(path, *args, **kw)
        self._patch = mock.patch("os.open", counting)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()


class CommandLineTests(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, timeout=60)

    def test_help(self):
        done = self.run_script("--help")
        self.assertEqual(done.returncode, 0)
        self.assertIn("--since", done.stdout)
        self.assertIn("uncommitted edits to tracked files are not listed", " ".join(done.stdout.split()))

    def test_usage_errors_are_redacted_too(self):
        token = "ghp_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3z5A"
        for args in (("--format", token), ("--max-files", token), ("--" + token,)):
            with self.subTest(args=args[0]):
                done = self.run_script(*args)
                self.assertEqual(done.returncode, 2)
                self.assertNotIn(token, done.stderr)
                self.assertIn("ghp_****", done.stderr)

    def test_json_and_text(self):
        root = os.path.join(FIXTURES, "rust-cli-lib")
        done = self.run_script("--root", root, "--format", "json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["tool"], "discover")
        done = self.run_script("--root", root, "--format", "text")
        self.assertEqual(done.returncode, 0)
        self.assertIn("terminal/cli", done.stdout)
        self.assertIn("wordfreq", done.stdout)

    def test_json_is_the_default_off_a_terminal(self):
        done = self.run_script("--root", os.path.join(FIXTURES, "ts-library"))
        self.assertEqual(json.loads(done.stdout)["kinds"][0]["kind"], "library")

    def test_output_redacts_secret_shaped_values(self):
        # Assembled so that this file holds no secret-shaped value.
        token = "ghp_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3z5A"
        slack = "xoxa-" + "2-1234567890-abcdefghij"
        key = "-----BEGIN RSA " + "PRIVATE KEY-----\nMIIEow" + "IBAAKCAQEA\n-----END RSA " + "PRIVATE KEY-----"
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "package.json"), "w") as f:
                json.dump({"name": "tool", "description": f"Uses {token}, then {key}", "bin": {token: "cli.js"},
                           "repository": f"https://{slack}@github.com/o/r", "homepage": "https://me:pw1234@x.org/",
                           "scripts": {"deploy": "curl -u admin:SCRIPTBODY https://x.org"}}, f)
            with open(os.path.join(tmp, "cli.js"), "w") as f:
                f.write("#!/usr/bin/env node\n")
            for fmt in ("json", "text"):
                with self.subTest(fmt=fmt):
                    done = self.run_script("--root", tmp, "--format", fmt)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    self.assertIn("ghp_****", done.stdout)
                    for value in (token, slack, "MIIEowIBAAKCAQEA", "pw1234", "SCRIPTBODY"):
                        self.assertNotIn(value, done.stdout)
            manifest = json.loads(self.run_script("--root", tmp, "--format", "json").stdout)["manifests"][0]
            self.assertEqual((manifest["scripts"], manifest["homepage"], manifest["repository"]),
                             (["deploy"], "https://x.org/", "https://github.com/o/r"))

    def test_bad_usage_and_unreadable_root_exit_2(self):
        self.assertEqual(self.run_script("--root", os.path.join(FIXTURES, "missing")).returncode, 2)
        self.assertEqual(self.run_script("--root", os.path.join(FIXTURES, "qt-app", "README.md")).returncode, 2)
        self.assertEqual(self.run_script("--format", "xml").returncode, 2)
        self.assertEqual(self.run_script("--max-files", "0").returncode, 2)
        self.assertEqual(self.run_script("--bogus").returncode, 2)


if __name__ == "__main__":
    unittest.main()
