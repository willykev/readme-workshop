"""Tests for check_readme: every rule fails once and passes once, plus security and output."""

import builtins
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "skills" / "readme-workshop" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_readme  # noqa: E402

from fixturetree import materialize  # noqa: E402
FIXTURES = materialize(HERE / "fixtures" / "check")
SCRIPT = SCRIPTS / "check_readme.py"
WIDE = {"words": [0, 100000]}
# Secret-shaped values, assembled so that the test file itself holds none.
AWS_KEY = "AKIA" + "Q7X2" * 4
GH_TOKEN = "ghp_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3z5A"


class Base(unittest.TestCase):
    def tree(self, files=None):
        top = Path(tempfile.mkdtemp(prefix="rw-test-"))
        self.addCleanup(shutil.rmtree, top, True)
        root = top / "proj"
        root.mkdir()
        for rel, content in (files or {}).items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, int):  # a sparse file of that size
                with open(path, "wb") as fh:
                    fh.truncate(content)
            elif isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        return root

    def check(self, text, files=None, kinds=("library",), readme="README.md", config=WIDE, root=None):
        root = root if root is not None else self.tree(files)
        return check_readme.check(str(root), readme, text=text, kinds=list(kinds) if kinds else None,
                                  config=config)

    def ids(self, result, severity=None):
        return [f["id"] for f in result["findings"] if severity is None or f["severity"] == severity]

    def lines(self, result, rid):
        return [f["line"] for f in result["findings"] if f["id"] == rid]

    def message(self, result, rid):
        return next(f["message"] for f in result["findings"] if f["id"] == rid)

    def has(self, text, rid, **kw):
        result = self.check(text, **kw)
        self.assertIn(rid, self.ids(result), result["findings"])
        return result

    def lacks(self, text, rid, **kw):
        result = self.check(text, **kw)
        self.assertNotIn(rid, self.ids(result), result["findings"])
        return result


class PageErrors(Base):
    def test_rw001_missing_or_empty(self):
        self.assertEqual(self.ids(self.check(None)), ["RW001"])
        self.assertEqual(self.ids(self.check("  \n\n")), ["RW001"])
        self.lacks("# X\n\nText.\n", "RW001")

    def test_rw002_contract_placeholders(self):
        for text in ("# AppName\n", "Clone https://github.com/OWNER/tool.\n", "A [category] for x.\n",
                     "Windows: TBD\n", "TODO: write this\n", "Lorem ipsum dolor.\n",
                     "<!--\n  README.md for an app. Copy this file, fill it in.\n-->\n\n# X\n"):
            with self.subTest(text=text):
                self.has(text, "RW002")

    def test_rw002_leaves_real_text_alone(self):
        text = ("# Tool\n\n- [ ] open task\n- [x] done task\n\nPress [Enter] or [Ctrl+C]. See [1] and [...].\n\n"
                "> [!NOTE]\n> Careful.\n\nRun `todo add` or `TODO`, `[category](x)`, and `mytool sync OWNER/REPO`.\n\n"
                "```sh\n# TODO later\n```\n\nThe mytool sync OWNER/REPO command copies a repository.\n"
                "A footnote[^n] and a [ref].\n\n[^n]: Note.\n[ref]: https://example.com\n")
        self.lacks(text, "RW002")

    def test_rw002_template_copied_straight(self):
        for name in ("README.template.md", "guide.template.md"):
            text = (SCRIPTS.parent / "assets" / name).read_text(encoding="utf-8")
            with self.subTest(template=name):
                result = self.has(text, "RW002")
                message = " ".join(f["message"] for f in result["findings"] if f["id"] == "RW002")
                self.assertRegex(message, r"NAME|PLATFORM_OR_HOST|OWNER/|SYMPTOM")

    def test_rw002_acronyms_and_env_vars_pass(self):
        self.lacks("# Weather\n\nThe API reads AWS_REGION and HOME_DIR from the environment, and each "
                   "station needs a NAME and a LABEL in its CSV file. See the FAQ.\n", "RW002")

    def test_rw002_single_word_tokens_in_template_places(self):
        self.has("# NAME\n\nText.\n", "RW002")
        self.has("# Tool\n\nNAME is a CATEGORY for Linux.\n", "RW002")
        self.has("# Tool\n\n- **LABEL.** Does a thing.\n", "RW002")
        self.has("# Tool\n\n## TASK\n\nText.\n", "RW002")
        self.has("# Tool\n\nCATEGORY\n", "RW002")
        self.lacks("# NAME\n\nmytool - counts words\n\n# SYNOPSIS\n\nmytool FILE\n\n## WHY\n\nFIX the build.\n", "RW002")

    def test_rw003_unclosed_fence(self):
        result = self.has("# X\n\n```sh\nls\n", "RW003")
        self.assertEqual(self.lines(result, "RW003"), [3])
        self.lacks("# X\n\n```sh\nls\n```\n", "RW003")

    def test_rw004_missing_link_target(self):
        files = {"docs/guide.md": "# G\n", "my file.md": "x", "docs/sub/x.txt": "x"}
        self.has("[a](docs/missing.md)\n", "RW004", files=files)
        self.lacks("[a](docs/guide.md) [b](my%20file.md) [c](docs/) [d](docs/guide.md?raw=true) "
                   "[e](../../issues) [f](../../releases/latest) [g](https://example.com/x.md) "
                   "[h](mailto:a@b.c) [i](./docs/sub/x.txt)\n", "RW004", files=files)

    def test_rw005_anchor_in_this_page(self):
        text = "# Tool\n\n## Install\n\n## Install\n\n[a](#install-1) [b](#top) [c](#user-content-install) [d](#Install)\n"
        self.lacks(text, "RW005")
        self.has("# Tool\n\n## Install\n\n[a](#instal)\n", "RW005")

    def test_rw005_anchor_in_another_markdown_file(self):
        files = {"docs/guide.md": "# Guide\n\n## First steps\n\n## Keys & mouse\n", "src/a.py": "x\n"}
        self.lacks("[a](docs/guide.md#first-steps) [b](docs/guide.md#keys--mouse) [c](src/a.py#L3)\n",
                   "RW005", files=files)
        result = self.has("[a](docs/guide.md#last-steps)\n", "RW005", files=files)
        self.assertIn("docs/guide.md", self.message(result, "RW005"))

    def test_rw006_missing_image(self):
        files = {"shots/a.png": b"\x89PNG"}
        self.has("![A window with two notes](shots/b.png)\n", "RW006", files=files)
        self.has('<img src="shots/c.png" alt="A window with two notes">\n', "RW006", files=files)
        self.lacks("![A window with two notes](shots/a.png)\n", "RW006", files=files)

    def test_rw007_example_differs(self):
        files = {"examples/out.txt": "one  \ntwo\nthree\n\n"}
        ok = "<!-- matches: examples/out.txt -->\n```text\none\ntwo\nthree\n```\n"
        self.lacks(ok, "RW007", files=files)
        self.lacks("<!-- matches: examples/out.txt#L2-L3 -->\n```\ntwo\nthree\n```\n", "RW007", files=files)
        result = self.has(ok.replace("two", "TWO"), "RW007", files=files)
        self.assertIn("line 2", self.message(result, "RW007"))

    def test_rw008_marker_names_missing_file_or_range(self):
        files = {"examples/out.txt": "one\ntwo\n"}
        self.has("<!-- matches: examples/none.txt -->\n```\none\n```\n", "RW008", files=files)
        self.has("<!-- matches: examples/out.txt#L2-L5 -->\n```\ntwo\n```\n", "RW008", files=files)
        self.lacks("<!-- matches: examples/out.txt#L2 -->\n```\ntwo\n```\n", "RW008", files=files)

    def test_rw013_secrets(self):
        self.has("Use key %s.\n" % AWS_KEY, "RW013")
        self.has("```sh\nexport GH=%s\n```\n" % GH_TOKEN, "RW013")
        self.has("<!-- %s -->\n" % ("sk-proj-" + "a1B2c3D4e5F6g7H8i9J0k"), "RW013")
        self.has("```\n-----BEGIN RSA PRIVATE KEY-----\n" + "MIIEowIBAAKCAQEA" * 4 + "\n```\n", "RW013")
        self.lacks("Key AKIAIOSFODNN7EXAMPLE, token ghp_" + "x" * 36 + ", sk-your-key-goes-here-please, "
                   "xoxb-your-token, and -----BEGIN PRIVATE KEY----- headers.\n", "RW013")

    def test_rw014_file_url(self):
        self.has("[x](file:///etc/passwd)\n", "RW014")
        self.lacks("[x](docs/a.md) [y](/docs/a.md) ![z](docs/../docs/a.md)\n", "RW014", files={"docs/a.md": "# A\n"})
        # A file that is simply named "file" is a file, not a file: URL.
        result = self.check("# X\n\n[x](file) ![y](file)\n", files={"file": "x\n"})
        self.assertEqual(self.ids(result, "error"), [])

    def test_rw002_template_install_block(self):
        text = "# Tool\n\nTool turns notes into tasks.\n\n## Install\n\n```sh\nINSTALL_COMMAND\n```\n"
        self.assertEqual(self.lines(self.check(text), "RW002"), [8])
        self.lacks("# Tool\n\n## Install\n\n```sh\nexport API_TOKEN=x\npip install tool\n```\n", "RW002")


class Warnings(Base):
    def test_rw101_word_range(self):
        self.has("# X\n\nTen words of prose are not enough for an app page.\n", "RW101", kinds=["app"], config=None)
        self.lacks("# X\n\n" + "word " * 400 + "\n", "RW101", kinds=["app"], config=None)
        self.lacks("# X\n\nShort.\n", "RW101", files={".readme-workshop.json": '{"words": [1, 10]}'},
                   kinds=["app"], config=None)

    def test_rw101_widest_range_for_several_kinds(self):
        text = "# X\n\n" + "word " * 1400 + "\n"
        self.has(text, "RW101", kinds=["app"], config=None)
        self.lacks(text, "RW101", kinds=["app", "extension"], config=None)

    def test_rw102_install(self):
        self.has("# X\n\nWhat it is.\n", "RW102")
        self.has("# X\n\n" + "Text.\n\n" * 30 + "## Install\n\nRun it.\n", "RW102")
        self.lacks("# X\n\n## Install\n\nRun it.\n", "RW102")
        self.lacks("# X\n\n```sh\npip install x\n```\n", "RW102")
        self.lacks("# X\n\nWhat it is.\n", "RW102", kinds=["automation"])

    def test_rw103_badges(self):
        badge = "![b](https://img.shields.io/badge/%d-x-green)\n"
        self.has("# X\n" + "".join(badge % n for n in range(3)), "RW103")
        self.lacks("# X\n" + "".join(badge % n for n in range(2)), "RW103")

    def test_rw104_filler(self):
        self.has("# X\n\nA fast and simple tool.\n", "RW104")
        self.has("# X\n\n- An easy-to-use, blazing-fast parser\n", "RW104")
        self.lacks("# X\n\nStarts in 40 ms, which is fast enough. A broken build fails fast. "
                   "Keys are easy to get wrong. The Simple Storage Service holds files.\n", "RW104")

    def test_rw105_emoji_heading(self):
        self.has("# X\n\n## 🚀 Launch\n\nText.\n", "RW105")
        self.has("# X\n\n## :rocket: Launch\n\nText.\n", "RW105")
        self.lacks("# X\n\n## Launch → land\n\nText.\n", "RW105")

    def test_rw106_heavy_images(self):
        files = {"a.gif": 3_500_000 + 3 * 1024 * 1024 // 10, "b.png": 1_200_000, "c.png": 500_000, "d.gif": 2_000_000}
        result = self.check("![Loop of the board zooming](a.gif) ![Still of the board](b.png)\n\n"
                            "![Still of a list](c.png) ![Loop of a list](d.gif)\n", files=files)
        self.assertEqual(self.lines(result, "RW106"), [1, 1])

    def test_rw107_prompts(self):
        self.has("```sh\n$ make\n```\n", "RW107")
        self.has("```console\n$ make\n$ make install\n```\n", "RW107")
        self.lacks("```console\n$ make\nbuilt 3 files\n```\n", "RW107")
        self.lacks("```sh\nmake\ncat <<EOF\n> not a prompt\n```\n", "RW107")

    def test_rw108_speed_words(self):
        self.has("# X\n\nIt starts instantly.\n", "RW108")
        self.has("# X\n\nIt is faster than the rest.\n", "RW108")
        self.lacks("# X\n\nIt starts instantly: 40 ms on a laptop. It is 3x faster than v1.\n", "RW108")

    def test_rw109_toc_on_short_page(self):
        toc = "# X\n\n- [A](#a)\n- [B](#b)\n- [C](#c)\n- [D](#d)\n\n## A\n\nx\n\n## B\n\nx\n\n## C\n\nx\n\n## D\n\nx\n"
        self.has(toc, "RW109")
        self.lacks(toc + "\nmore\n" * 250, "RW109")

    def test_rw110_alt_text(self):
        files = {"shots/hero.png": b"x"}
        for alt in ("", "screenshot", "hero.png", "hero", "Demo"):
            with self.subTest(alt=alt):
                self.has("![%s](shots/hero.png)\n" % alt, "RW110", files=files)
        self.lacks("![The board with three notes joined by arrows](shots/hero.png) "
                   "![](https://img.shields.io/badge/x-y-green)\n", "RW110", files=files)

    def test_rw111_first_screen(self):
        top = "# X\n\n> **Note**\n> Beta.\n\n![a](https://img.shields.io/a) ![b](https://img.shields.io/b)\n<img src=\"logo.svg\" alt=\"The X logo\">\n"
        self.has(top + "\nX reads your notes and files each one by topic.\n", "RW111", files={"logo.svg": "<svg/>"})
        self.lacks("# X\n\nX reads your notes and files each one by topic.\n", "RW111")

    def test_rw113_empty_heading(self):
        result = self.has("# X\n\n## Empty\n\n<!-- later -->\n\n## Next\n\nText.\n", "RW113")
        self.assertEqual(self.lines(result, "RW113"), [3])
        self.lacks("# X\n\n## Parent\n\n### Child\n\nText.\n", "RW113")


class Manual(Base):
    def test_rw201_pictures(self):
        self.has("![The board with notes](a.png)\n", "RW201", files={"a.png": b"x"})
        self.lacks("![CI](https://img.shields.io/badge/ci-ok-green)\n", "RW201")

    def test_rw202_commands(self):
        self.has("```sh\nmake\n```\n", "RW202")
        self.lacks("```python\nprint(1)\n```\n", "RW202")

    def test_rw203_extension(self):
        self.has("# X\n\nText.\n", "RW203", kinds=["extension"])
        self.lacks("# X\n\nText.\n", "RW203", kinds=["library"])

    def test_rw204_example_file_too_large(self):
        self.has("<!-- matches: big.txt -->\n```\nx\n```\n", "RW204", files={"big.txt": 3 * 1024 * 1024})
        self.lacks("<!-- matches: small.txt -->\n```\nx\n```\n", "RW204", files={"small.txt": "x\n"})

    def test_rw114_when_discovery_fails(self):
        # A failed discovery is a warning, so --strict cannot pass without the code comparisons.
        broken = types.ModuleType("discover")
        broken.scan = mock.Mock(side_effect=RuntimeError("boom"))
        with mock.patch.dict(sys.modules, {"discover": broken}):
            result = self.check("# X\n\n## Install\n\nText.\n", kinds=None)
        self.assertIn("RW114", self.ids(result, "warning"))
        self.assertNotIn("RW204", self.ids(result))
        self.assertEqual(result["kinds"], [])


class Parity(Base):
    """Rules that compare the page with the project, on the fixture trees."""

    def fixture(self, name, readme="README.md", kinds=("library",)):
        return check_readme.check(str(FIXTURES / name), readme, kinds=list(kinds), config=WIDE)

    def test_good_fixtures_have_no_errors(self):
        for name in ("hello-action", "skill-kit", "mcp-server", "cli-tool"):
            with self.subTest(name=name):
                result = self.fixture(name)
                self.assertEqual(self.ids(result, "error") + self.ids(result, "warning"), [], result["findings"])

    def test_rw009_action_inputs_and_outputs(self):
        result = self.fixture("hello-action", "README-bad.md")
        messages = [f["message"] for f in result["findings"] if f["id"] == "RW009"]
        self.assertEqual(len(messages), 4, messages)
        self.assertTrue(any("color" in m and "snippet" in m for m in messages))
        self.assertTrue(any("greeting" in m for m in messages))
        self.assertTrue(any("token" in m and "never mentioned" in m for m in messages))

    def test_rw112_action_from_a_branch(self):
        self.assertEqual(self.lines(self.fixture("hello-action", "README-bad.md"), "RW112"), [10])
        self.assertNotIn("RW112", self.ids(self.fixture("hello-action")))

    def test_rw010_command_not_in_bins(self):
        self.assertIn("RW010", self.ids(self.fixture("cli-tool", "README-bad.md")))
        self.assertNotIn("RW010", self.ids(self.fixture("cli-tool")))

    def test_rw011_mcp_tool_not_registered(self):
        result = self.fixture("mcp-server", "README-bad.md")
        self.assertEqual(self.lines(result, "RW011"), [17])
        self.assertNotIn("RW011", self.ids(self.fixture("mcp-server")))

    def test_rw012_plugin_and_skill_names(self):
        result = self.fixture("skill-kit", "README-bad.md")
        self.assertEqual(self.lines(result, "RW012"), [9, 15])
        self.assertNotIn("RW012", self.ids(self.fixture("skill-kit")))

    def test_rw012_leaves_other_plugins_alone(self):
        text = ("# Skill kit\n\nNeeds the helper first: `/plugin install superpowers@official`, and "
                "`gh skill install github/awesome-copilot documentation-writer`.\n")
        result = check_readme.check(str(FIXTURES / "skill-kit"), text=text, kinds=["library"], config=WIDE)
        self.assertNotIn("RW012", self.ids(result))

    def test_rw012_ignores_repo_slugs_and_urls_in_plugin_install(self):
        root = self.tree({"plugin.json": '{"name": "acme-cli"}'})
        text = ("# acme-cli\n\n```sh\ngrok plugin install acme-labs/acme-cli --trust\n"
                "agy plugin install https://github.com/acme-labs/acme-cli\n```\n")
        self.lacks(text, "RW012", root=root)
        http_root = self.tree({"plugin.json": '{"name": "http"}'})
        self.lacks("# http\n\n```sh\nagy plugin install https://github.com/acme/http\n```\n", "RW012", root=http_root)

    def test_kinds_come_from_discovery(self):
        result = check_readme.check(str(FIXTURES / "hello-action"), config=WIDE)
        self.assertIn("automation", result["kinds"])

    def test_good_page_is_clean(self):
        result = check_readme.check(str(FIXTURES / "good"))
        self.assertEqual(result["kinds"], ["terminal"])
        self.assertEqual(result["totals"]["error"] + result["totals"]["warning"], 0, result["findings"])
        self.assertEqual(result["facts"]["code_blocks"], 4)


MCP_PY = "from mcp.server.fastmcp import FastMCP\nmcp = FastMCP('x')\n"
TOOL_TABLE = "# X\n\n## Tools\n\n| Tool | What it does |\n| --- | --- |\n| `first` | One |\n| `later` | Two |\n"


class Completeness(Base):
    """Parity rules do not call a name absent when discovery could not read the whole project."""

    def test_rw011_not_claimed_past_a_module_too_large_to_read(self):
        result = self.check(TOOL_TABLE, {
            "server.py": MCP_PY + "\n@mcp.tool()\ndef first() -> None:\n    pass\n",
            "more_tools.py": MCP_PY + "\n@mcp.tool()\ndef later() -> None:\n    pass\n" + "# padding\n" * 30000})
        self.assertNotIn("RW011", self.ids(result))
        self.assertEqual(self.ids(result, "warning").count("RW114"), 1)
        self.assertIn("later", self.message(result, "RW114"))
        self.assertIn("more_tools.py", self.message(result, "RW114"))

    def test_rw011_not_claimed_for_a_tool_named_by_a_variable(self):
        result = self.check(TOOL_TABLE, {"server.py": MCP_PY + "NAME = 'later'\n\n@mcp.tool()\ndef first() -> None:\n"
                                         "    pass\n\n@mcp.tool(name=NAME)\ndef run() -> None:\n    pass\n"})
        self.assertNotIn("RW011", self.ids(result))
        self.assertEqual(self.ids(result, "warning").count("RW114"), 1)

    def test_rw011_still_reported_when_discovery_read_everything(self):
        result = self.check(TOOL_TABLE, {"server.py": MCP_PY + "\n@mcp.tool()\ndef first() -> None:\n    pass\n",
                                         "package-lock.json": "{}" + " " * 300000})
        self.assertEqual(self.lines(result, "RW011"), [8])
        self.assertNotIn("RW114", self.ids(result))

    def test_rw010_not_claimed_beside_a_malformed_manifest(self):
        files = {name: (FIXTURES / "cli-tool" / name).read_text() for name in
                 ("pyproject.toml", "notely/__init__.py", "notely/cli.py", "README-bad.md")}
        self.assertIn("RW010", self.ids(self.check(None, files, readme="README-bad.md")))
        files["plugins/pyproject.toml"] = 'project = "broken"\n'
        result = self.check(None, files, readme="README-bad.md")
        self.assertNotIn("RW010", self.ids(result))
        self.assertIn("RW114", self.ids(result, "warning"))


    def test_rw011_not_claimed_when_every_tool_name_is_computed(self):
        table = TOOL_TABLE.replace("`first`", "`search`")
        result = self.check(table, {"server.py": MCP_PY + "NAME = 'search'\n\n@mcp.tool(name=NAME)\ndef run() -> None:\n"
                                    "    pass\n"}, kinds=("extension",))
        self.assertNotIn("RW011", self.ids(result))
        self.assertEqual(self.ids(result, "warning").count("RW114"), 1)
        self.assertIn("search, later", self.message(result, "RW114"))
        # A project that is no MCP server keeps its tables to itself.
        self.assertNotIn("RW114", self.ids(self.check(table, {"lib.py": "def search():\n    pass\n"})))

    def test_rw011_follows_a_server_made_in_another_module(self):
        files = {"pkg/app.py": MCP_PY + "\n@mcp.tool()\ndef first() -> None:\n    pass\n",
                 "pkg/more.py": "from pkg.app import mcp\n\n\n@mcp.tool()\ndef later() -> None:\n    pass\n"}
        result = self.check(TOOL_TABLE, files, kinds=("extension",))
        self.assertEqual([i for i in self.ids(result) if i in ("RW011", "RW114")], [])
        result = self.check(TOOL_TABLE.replace("`later`", "`gone`"), files, kinds=("extension",))
        self.assertEqual(self.lines(result, "RW011"), [8])

    def test_rw011_not_claimed_past_the_registration_limit(self):
        tools = "".join("@mcp.tool()\ndef tool_%03d() -> None:\n    pass\n\n" % k for k in range(301))
        table = TOOL_TABLE.replace("`first`", "`tool_000`").replace("`later`", "`tool_300`")
        result = self.check(table, {"server.py": MCP_PY + tools}, kinds=("extension",))
        self.assertNotIn("RW011", self.ids(result))
        self.assertIn("tool_300", self.message(result, "RW114"))

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "permissions do not stop this user reading")
    def test_rw011_not_claimed_past_a_module_that_cannot_be_read(self):
        root = self.tree({"server.py": MCP_PY + "\n@mcp.tool()\ndef first() -> None:\n    pass\n",
                          "more.py": MCP_PY + "\n@mcp.tool()\ndef later() -> None:\n    pass\n"})
        (root / "more.py").chmod(0)
        self.addCleanup((root / "more.py").chmod, 0o644)
        result = self.check(TOOL_TABLE, root=root, kinds=("extension",))
        self.assertNotIn("RW011", self.ids(result))
        self.assertIn("more.py (could not be read)", self.message(result, "RW114"))

    def test_rw010_not_claimed_beside_a_manifest_that_does_not_parse(self):
        files = {name: (FIXTURES / "cli-tool" / name).read_text() for name in
                 ("pyproject.toml", "notely/__init__.py", "notely/cli.py", "README-bad.md")}
        files["plugins/pyproject.toml"] = "[project\nname = \n"
        result = self.check(None, files, readme="README-bad.md")
        self.assertNotIn("RW010", self.ids(result))
        self.assertIn("plugins/pyproject.toml (is not valid TOML)", self.message(result, "RW114"))

    def test_a_malformed_marketplace_is_reported_and_the_check_goes_on(self):
        files = {".claude-plugin/plugin.json": '{"name": "kit"}',
                 ".claude-plugin/marketplace.json": '{"name": ["kit"], "plugins": {"name": "kit"}}'}
        result = self.check("# Kit\n\n[x](gone.md)\n\n```sh\nclaude plugin install kitt@kit\n```\n", files,
                            kinds=("extension",))
        self.assertIn("RW004", self.ids(result, "error"))
        self.assertIn("marketplace name", self.message(result, "RW204"))


ACTION_YML = "name: Widget\ndescription: Does it.\ninputs:\n  file:\n    description: A file.\nruns:\n  using: composite\n" \
             "  steps:\n    - shell: bash\n      run: echo\n"


class ActionIdentity(Base):
    """RW009 and RW112 apply to this project's own Actions, wherever they sit."""

    def widget(self, remote="https://github.com/me/widget.git", files=None):
        top = Path(tempfile.mkdtemp(prefix="rw-test-"))
        self.addCleanup(shutil.rmtree, top, True)
        root = top / "widget"
        (root / ".git").mkdir(parents=True)
        (root / ".git" / "config").write_text('[remote "origin"]\n\turl = %s\n' % remote if remote else "")
        for rel, text in {"action.yml": ACTION_YML, **(files or {})}.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)
        return root

    def snippet(self, body):
        return "# Widget\n\n## Usage\n\n```yaml\nsteps:\n%s```\n\nSet `file` to the file to read.\n" % body

    def test_another_owners_action_of_the_same_name_is_left_alone(self):
        root = self.widget()
        other = self.check(self.snippet("  - uses: other/widget@v1\n    with:\n      color: blue\n"), root=root)
        self.assertNotIn("RW009", self.ids(other))
        own = self.check(self.snippet("  - uses: me/widget@v1\n    with:\n      color: blue\n"), root=root)
        self.assertEqual(self.lines(own, "RW009"), [9])
        # With no remote or manifest naming an owner, the folder's name identifies the Action, as before.
        unknown = self.check(self.snippet("  - uses: someone/widget@v1\n    with:\n      color: blue\n"),
                             root=self.widget(remote=None))
        self.assertEqual(self.lines(unknown, "RW009"), [9])

    def test_with_in_flow_form_or_before_uses(self):
        root = self.widget()
        flow = self.check(self.snippet("  - uses: me/widget@v1\n    with: {file: a.md, typo: 1}\n"), root=root)
        self.assertEqual([(f["line"], "typo" in f["message"]) for f in flow["findings"] if f["id"] == "RW009"],
                         [(8, True)])
        before = self.check(self.snippet("  - name: Run it\n    with:\n      file: a.md\n      typo: 1\n"
                                         "    uses: me/widget@v1\n  - uses: actions/checkout@v4\n"
                                         "    with:\n      fetch-depth: 0\n"), root=root)
        self.assertEqual(self.lines(before, "RW009"), [10])

    def test_nested_action_is_found_by_its_path(self):
        nested = ACTION_YML.replace("file:", "target:")
        root = self.widget(files={"actions/build/action.yml": nested})
        text = self.snippet("  - uses: me/widget/actions/build@main\n    with:\n      target: x\n      file: y\n"
                            "  - uses: me/widget@v1\n    with:\n      file: z\n")
        result = self.check(text, root=root)
        self.assertEqual(self.lines(result, "RW112"), [7])
        self.assertEqual(self.lines(result, "RW009"), [10])
        self.assertIn("file", self.message(result, "RW009"))


class Security(Base):
    def test_outside_targets_are_reported_and_never_opened(self):
        top = Path(tempfile.mkdtemp(prefix="rw-sec-"))
        self.addCleanup(shutil.rmtree, top, True)
        out = top / "outside"
        out.mkdir()
        (out / "secret.md").write_text("# Secret\n\n## Part\n")
        (out / "pic.png").write_bytes(b"\x89PNG" + b"x" * 2_000_000)
        (out / "data.txt").write_text("x\n")
        root = top / "proj"
        (root / "sub").mkdir(parents=True)
        symlink(out / "secret.md", root / "link.md")
        symlink(out / "pic.png", root / "pic.png")
        symlink(out / "data.txt", root / "data.txt")
        symlink(out, root / "sub" / "away")
        text = ("# X\n\n[a](../../etc/passwd) [b](/etc/passwd) [c](link.md#part) ![d](pic.png)\n"
                "[e](sub/away/secret.md#secret) [f](../outside/secret.md) <a href=\"C:/Windows/x.md\">g</a>\n\n"
                "<!-- matches: data.txt -->\n```\nx\n```\n")
        with OpenSpy() as spy:
            result = self.check(text, root=root)
        opened = spy.paths
        self.assertEqual(self.ids(result, "error"), ["RW014"] * 8, result["findings"])
        self.assertEqual([p for p in opened if p.startswith(str(out.resolve()))], [])
        assets = str((SCRIPTS.parent / "assets").resolve())
        self.assertEqual([p for p in opened if not p.startswith((str(root.resolve()), assets))], [])

    def test_pathological_markdown_stays_fast(self):
        root = self.tree()
        for text in ("[" * 300000, "".join("`" * k + " x " for k in range(1, 700)), "[a](b) " * 100000,
                     ("Fast. " * 40 + "\n") * 2000, "![a](b.png)\n" * 10000):
            started = time.monotonic()
            self.check(text, root=root)
            self.assertLess(time.monotonic() - started, 20)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes need POSIX")
    def test_named_pipes_are_not_read(self):
        root = self.tree()
        os.mkfifo(root / "pipe.md")
        os.mkfifo(root / "pipe.txt")
        result = self.check("[a](pipe.md#x)\n\n<!-- matches: pipe.txt -->\n```\nx\n```\n", root=root)
        self.assertEqual(self.ids(result, "error"), ["RW008"])

    def test_readme_outside_root_is_bad_usage(self):
        with self.assertRaises(check_readme.UsageError):
            check_readme.check(str(self.tree()), "../README.md")

    def test_symlinked_readme_outside_root_is_bad_usage(self):
        root = self.tree()
        (root.parent / "elsewhere.md").write_text("# X\n")
        symlink(root.parent / "elsewhere.md", root / "README.md")
        with self.assertRaises(check_readme.UsageError):
            check_readme.check(str(root))

    def test_long_digit_runs_and_many_anchor_links_stay_fast(self):
        root = self.tree()
        heads = "".join("## Part %d\n\nText.\n\n" % n for n in range(3000))
        for text in ("Fast " + "1" * 300000 + "\n", heads + "[a](#part-1) " * 30000 + "\n"):
            started = time.monotonic()
            self.check(text, root=root)
            self.assertLess(time.monotonic() - started, 5)

    def test_control_characters_and_url_passwords_never_reach_output(self):
        root = self.tree()
        text = "# X\n\n[a](gone\x1b[31m.md) [b](https://user:hunter2@example.org/x.md)\n\n## \x1b]0;title\x07Go\n"
        for fmt in ("text", "json", "github"):
            with self.subTest(fmt=fmt):
                proc = run_cli("--root", root, "--stdin", "--kind", "library", "--format", fmt, input=text)
                self.assertNotIn("\x1b", proc.stdout)
                self.assertNotIn("\x07", proc.stdout)
                self.assertIn("gone\\x1b[31m.md", proc.stdout.replace("\\\\", "\\"))
        self.assertNotIn("hunter2", check_readme.redact("see https://user:hunter2@example.org/x"))
        self.assertNotIn("hunter2", check_readme.redact("see https://:hunter2@example.org/x"))  # no user name
        result = self.check("# X\n\n[b](https://:hunter2@example.org/x.md) [c](file://:hunter2@host/x)\n", root=root)
        self.assertNotIn("hunter2", json.dumps(result))
        self.assertIn("RW014", self.ids(result))
        proc = run_cli("--root", root, "--readme", "x\n::error::forged/../../y.md")
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("\n::error", proc.stderr)

    def test_reads_refuse_a_folder_swapped_for_a_symlink(self):
        # The path was resolved inside the root; by the time it is opened, a folder on it leads outside.
        top = self.tree().parent
        root = top / "proj"
        (root / "docs").mkdir()
        (root / "docs" / "a.md").write_text("# A\n")
        (top / "away").mkdir()
        (top / "away" / "a.md").write_text("# Outside\n")
        os.rename(root / "docs", root / "docs.real")
        symlink(top / "away", root / "docs")
        with mock.patch("os.path.realpath", side_effect=lambda p, **kw: os.path.abspath(p)):
            self.assertIsNone(check_readme.Root(root).read(str(root / "docs" / "a.md")))

    def test_secrets_redacted_in_every_format(self):
        root = self.tree({"docs/a.md": "# A\n"})
        text = "# X\n\nKey %s and `%s`.\n\n[doc](docs/%s.md)\n" % (AWS_KEY, GH_TOKEN, AWS_KEY)
        for fmt in ("text", "json", "github"):
            with self.subTest(fmt=fmt):
                proc = run_cli("--root", root, "--stdin", "--kind", "library", "--format", fmt, input=text)
                self.assertEqual(proc.returncode, 1)
                self.assertNotIn(AWS_KEY, proc.stdout)
                self.assertNotIn(GH_TOKEN, proc.stdout)
                self.assertIn("AKIA****", proc.stdout)
        result = self.check(text, root=root)
        self.assertEqual(self.ids(result, "error").count("RW013"), 3)
        self.assertNotIn(AWS_KEY, json.dumps(result))

    def test_redaction_covers_more_token_shapes(self):
        samples = ["xox%s-" % k + "2-1234567890-abcdefghij" for k in "abposr"]
        samples.append("xapp-" + "1-A0123456789-1234567890123-abcdef0123456789")
        for value in samples:
            with self.subTest(value=value[:5]):
                self.assertNotIn(value, check_readme.redact("token %s here" % value))
                self.assertEqual(self.ids(self.check("# X\n\nUse %s.\n" % value), "error"), ["RW013"])
        key = "-----BEGIN OPENSSH " + "PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA\n-----END OPENSSH " + "PRIVATE KEY-----"
        self.assertNotIn("b3BlbnNzaC1rZXktdjEAAAAA", check_readme.redact("a %s b" % key))
        self.assertNotIn("b3BlbnNzaC1rZXktdjEAAAAA", check_readme.redact("a %s" % key[:60]))

    def test_secret_files_are_never_read(self):
        root = self.tree({".env": "TOKEN=hunter2\n", "secrets/notes.md": "# Notes\n", "config/credentials.md": "# C\n",
                          "docs/a.md": "# A\n"})
        symlink(root / ".env", root / "docs" / "env.txt")
        text = ("# X\n\n[a](secrets/notes.md#notes) [b](config/credentials.md#nope) [c](docs/a.md#a)\n\n"
                "<!-- matches: .env -->\n```\nTOKEN=hunter1\n```\n\n<!-- matches: docs/env.txt -->\n```\nTOKEN=x\n```\n")
        with OpenSpy() as spy:
            result = self.check(text, root=root, kinds=("library",))
        opened = spy.paths
        secret = [str((root / p).resolve()) for p in (".env", "secrets", "secrets/notes.md", "config/credentials.md")]
        self.assertEqual([p for p in opened if p in secret], [])
        self.assertIn(str((root / "docs" / "a.md").resolve()), opened)
        self.assertNotIn("RW007", self.ids(result))
        self.assertEqual(self.ids(result, "error"), [])
        notes = [f for f in result["findings"] if f["id"] == "RW204"]
        self.assertEqual(len(notes), 4, result["findings"])
        self.assertTrue(all("secrets file" in f["message"] for f in notes))

    def test_nul_in_targets_is_a_broken_target_not_a_crash(self):
        root = self.tree({"docs/a.md": "# A\n", "data.txt": "x\n"})
        text = ("# X\n\n[a](docs/a%00.md#a) ![b](pic%00.png) [c](/abs%00)\n\n"
                "<!-- matches: data\x00.txt -->\n```\nx\n```\n")
        result = self.check(text, root=root)
        self.assertEqual(sorted(self.ids(result, "error")), ["RW004", "RW006", "RW008", "RW014"])
        self.assertNotIn("\x00", json.dumps(result, ensure_ascii=False))
        self.assertIn("docs/a%00.md", self.message(result, "RW004"))
        for fmt in ("text", "json", "github"):
            with self.subTest(fmt=fmt):
                proc = run_cli("--root", root, "--stdin", "--kind", "library", "--format", fmt, input=text)
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertEqual(proc.stderr, "")

    def test_main_never_prints_a_traceback(self):
        stderr = io.StringIO()
        with mock.patch.object(check_readme, "check", side_effect=ValueError("embedded null byte")), \
                contextlib.redirect_stderr(stderr):
            self.assertEqual(check_readme.main(["--root", str(self.tree())]), 2)
        self.assertIn("check_readme:", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes need POSIX")
    def test_reads_refuse_a_file_swapped_for_a_pipe(self):
        # The file checks pass, then the file is replaced before it is opened.
        root = self.tree()
        os.mkfifo(root / "README.md")
        done = []
        with mock.patch("os.path.isfile", return_value=True):
            reader = threading.Thread(target=lambda: done.append(check_readme.Root(root).read(str(root / "README.md"))),
                                      daemon=True)
            reader.start()
            reader.join(5)
        self.assertEqual(done, [None], "a named pipe was opened for reading")


class Boundary(Base):
    """Every project file the checker reads passes one check: inside the root, and no secrets file."""

    def test_a_readme_that_is_or_leads_to_a_secrets_file_is_refused_unread(self):
        root = self.tree({"credentials.md": "# FIXTURE-ONLY-HEADING\n", ".env": "TOKEN=x\n", "docs/a.md": "# A\n"})
        symlink(root / ".env", root / "README.md")
        for readme in ("credentials.md", "README.md"):
            with self.subTest(readme=readme):
                with OpenSpy() as spy, self.assertRaises(check_readme.UsageError) as err:
                    check_readme.check(str(root), readme, kinds=["library"], config=WIDE)
                self.assertIn("secrets file", str(err.exception))
                self.assertEqual([p for p in spy.paths if p.endswith(("credentials.md", ".env"))], [])
                proc = run_cli("--root", root, "--readme", readme, "--kind", "library")
                self.assertEqual(proc.returncode, 2)
                self.assertNotIn("FIXTURE-ONLY-HEADING", proc.stdout + proc.stderr)

    def test_configs_and_nested_actions_in_secrets_folders_are_refused(self):
        root = self.tree({"secrets/c.json": '{"ignore": ["RW004"]}',
                          "secrets/action/action.yml": ACTION_YML.replace("file:", "token:")})
        with self.assertRaises(check_readme.UsageError):
            check_readme.check(str(root), text="# X\n", config="secrets/c.json")
        with self.assertRaises(check_readme.UsageError):
            check_readme.check(str(root), text="# X\n", config=str(root / "secrets" / "c.json"))
        text = "# X\n\n## Usage\n\n```yaml\nsteps:\n  - uses: ./secrets/action\n    with:\n      color: x\n```\n"
        with OpenSpy() as spy:
            result = self.check(text, root=root, kinds=("automation",))
        self.assertEqual([p for p in spy.paths if "action.yml" in p], [])
        self.assertNotIn("RW009", self.ids(result))
        self.assertIn("secrets folder", self.message(result, "RW204"))

    def test_a_root_moved_away_mid_check_is_not_followed(self):
        top = self.tree({"docs/a.md": "# Inside\n"}).parent
        (top / "away" / "docs").mkdir(parents=True)
        (top / "away" / "docs" / "a.md").write_text("# Outside\n")
        root = check_readme.Root(top / "proj")
        self.addCleanup(root.close)
        os.rename(top / "proj", top / "proj.moved")
        symlink(top / "away", top / "proj")
        # Held open on POSIX, the pinned root still reads its own file; elsewhere the read is refused.
        self.assertIn(root.read("docs/a.md"), ("# Inside\n", None))
        with mock.patch.object(check_readme.safety, "WALK_BY_FD", False):
            fallback = check_readme.Root(top / "proj.moved")
            self.addCleanup(fallback.close)
            os.rename(top / "proj.moved", top / "proj.again")
            self.assertIsNone(fallback.read("docs/a.md"))

    def test_reads_by_name_refuse_a_folder_swapped_while_opening(self):
        # Where folders cannot be opened one below the other (Windows), a file is opened by its name, then
        # checked: the folders on its path must be the ones validated, so a swap during the open is caught.
        top = self.tree({"docs/a.md": "# Inside\n"}).parent
        root = top / "proj"
        (top / "away").mkdir()
        (top / "away" / "a.md").write_text("# Outside\n")
        real_open = os.open

        def swapping_open(path, flags, *args, **kw):
            if str(path).endswith("a.md") and not os.path.islink(root / "docs"):
                os.rename(root / "docs", root / "docs.real")
                symlink(top / "away", root / "docs")
                try:
                    return real_open(path, flags, *args, **kw)
                finally:  # put back before anything checks the path again
                    os.remove(root / "docs")
                    os.rename(root / "docs.real", root / "docs")
            return real_open(path, flags, *args, **kw)

        with mock.patch.object(check_readme.safety, "WALK_BY_FD", False):
            tree = check_readme.safety.Tree(root)
            self.addCleanup(tree.close)
            self.assertTrue(tree.read_bytes("docs/a.md", 100).startswith(b"# Inside"))
            with mock.patch("os.open", swapping_open):
                self.assertIsNone(tree.read_bytes("docs/a.md", 100))
            # And a folder that is a link when the file is opened is never followed.
            os.rename(root / "docs", root / "docs.real")
            symlink(top / "away", root / "docs")
            with mock.patch("os.path.realpath", side_effect=lambda p, **kw: os.path.abspath(p)):
                self.assertIsNone(check_readme.Root(root).read(str(root / "docs" / "a.md")))


class Bounds(Base):
    """What a large or hostile page costs stays bounded, and is reported once."""

    def test_blank_input_is_never_parsed(self):
        calls = []
        real = check_readme.mdfacts.facts
        with mock.patch.object(check_readme.mdfacts, "facts", lambda text, **kw: calls.append(len(text)) or real(text, **kw)):
            result = self.check(" \n\t\n" * 100000)
        self.assertEqual(self.ids(result), ["RW001"])
        self.assertEqual(calls, [0])

    def test_findings_are_capped_with_one_note(self):
        text = "# X\n\n" + "".join("[a](gone%d.md)\n" % k for k in range(700))
        result = self.check(text)
        self.assertEqual(len(result["findings"]), check_readme.MAX_FINDINGS + 1)
        note = result["findings"][-1]
        self.assertEqual((note["id"], note["line"]), ("RW114", None))
        self.assertIn("more findings than the 500 listed", note["message"])
        self.assertEqual(result["totals"]["error"], 700)  # the totals, and so the exit status, count them all
        listed = self.lines(result, "RW004")
        self.assertEqual(listed, list(range(3, 3 + len(listed))))

    def test_declared_names_are_listed_at_most_ten_times(self):
        inputs = "".join("  in%02d:\n    description: x\n" % k for k in range(30))
        root = self.tree({"action.yml": "name: W\ndescription: d\ninputs:\n%sruns:\n  using: composite\n" % inputs})
        text = "# W\n\n## Usage\n\n```yaml\nsteps:\n  - uses: ./\n    with:\n" + "".join(
            "      typo%d: 1\n" % k for k in range(5)) + "```\n"
        result = self.check(text, root=root, kinds=("automation",))
        fixes = [f["fix"] for f in result["findings"] if f["id"] == "RW009"]
        self.assertEqual(len(fixes), 5)
        self.assertTrue(all(f.endswith("in09 and 20 more.") for f in fixes), fixes[0])

    def test_a_linked_file_is_read_once_and_counts_against_the_budget(self):
        body = "# A\n\n" + "x\n" * 1000
        root = self.tree({"docs/a.md": body, "docs/b.md": body, "data.txt": "x\n"})
        opened = {}
        for copies in (1, 50):
            text = "# X\n\n" + "[a](docs/a.md#a) [b](docs/a.md#nope)\n" * copies + \
                "<!-- matches: data.txt -->\n```\nx\n```\n" * copies
            with OpenSpy() as spy:
                result = self.check(text, root=root)
            opened[copies] = [p for p in spy.paths if p.endswith(("a.md", "data.txt"))]
            self.assertEqual(self.ids(result, "error").count("RW005"), copies)
        self.assertEqual(opened[50], opened[1])  # discovery's look, then one read each
        # Past the budget, nothing more is read, links and examples alike, and one RW114 says so.
        text = "# X\n\n[a](docs/a.md#nope)\n\n[b](docs/b.md#nope)\n\n<!-- matches: data.txt -->\n```\nother\n```\n"
        with mock.patch.object(check_readme, "LINKED_BUDGET", len(body)), \
                mock.patch.object(check_readme.Context, "scan", lambda self: {}), OpenSpy() as spy:  # no discovery
            result = self.check(text, root=root)
        self.assertEqual([p for p in spy.paths if p.endswith(("b.md", "data.txt"))], [])
        self.assertEqual(self.lines(result, "RW005"), [3])
        self.assertEqual(self.ids(result).count("RW114"), 1)
        self.assertNotIn("RW007", self.ids(result))

    def test_anchors_in_a_linked_file_too_large_to_read_are_reported(self):
        root = self.tree({"docs/big.md": "# Big\n" + "x" * (check_readme.MAX_OTHER + 10)})
        result = self.check("# X\n\n[a](docs/big.md#one) [b](docs/big.md#two)\n\n[c](docs/big.md)\n", root=root)
        self.assertNotIn("RW005", self.ids(result))
        notes = [f for f in result["findings"] if f["id"] == "RW204"]
        self.assertEqual([f["line"] for f in notes], [3])
        self.assertIn("#one, #two", notes[0]["message"])


class LinksAndSnippets(Base):
    def test_rw014_for_a_file_autolink(self):
        result = self.check("# X\n\nSee <file:///local/example> and <https://example.org/x.md>.\n")
        self.assertEqual(self.ids(result, "error"), ["RW014"])

    def test_links_to_this_page_by_name_use_the_text_being_checked(self):
        root = self.tree({"README.md": "# Old\n"})
        result = self.check("# Intro\n\n[a](README.md#intro) [b](./README.md#old) [c](README.md)\n", root=root)
        self.assertEqual(self.ids(result, "error"), ["RW005"])
        self.assertEqual(self.lines(result, "RW005"), [3])
        result = self.check("# Intro\n\n[a](../README.md#intro)\n", readme="docs/README.md", root=self.tree())
        self.assertEqual(self.ids(result, "error"), ["RW004"])
        result = self.check("# Intro\n\n[a](../docs/README.md#intro)\n", readme="docs/README.md", root=self.tree())
        self.assertEqual(self.ids(result, "error"), [])

    def test_rw009_sees_a_step_across_a_comment_line(self):
        root = self.tree({"action.yml": ACTION_YML})
        snippet = "# W\n\n## Usage\n\n```yaml\nsteps:\n  - uses: ./\n# A comment, at any indent.\n    with:\n" \
                  "      stale: 1\n        # deeper\n      file: x\n```\n"
        result = self.check(snippet, root=root, kinds=("automation",))
        self.assertEqual(self.lines(result, "RW009"), [10])


class Output(Base):
    def test_github_escaping(self):
        self.assertEqual(check_readme.gh_data("50% done\r\nnext"), "50%25 done%0D%0Anext")
        self.assertEqual(check_readme.gh_prop("a:b,c%\n"), "a%3Ab%2Cc%25%0A")

    @unittest.skipIf(os.name == "nt", "Windows file names cannot hold a colon")
    def test_github_annotation_for_awkward_file_name(self):
        root = self.tree({"we,ird:na%me.md": "# X\n\n[x](<100%25 sure.md>) <a href=\"no\nwhere.md\">y</a>\n"})
        proc = run_cli("--root", ".", "--readme", "we,ird:na%me.md", "--kind", "library", "--format", "github",
                       cwd=root)
        notes = [l for l in proc.stdout.splitlines() if l.startswith("::error")]
        self.assertEqual(len(notes), 2, proc.stdout)
        self.assertTrue(notes[0].startswith("::error file=we%2Cird%3Ana%25me.md,line=3,title=RW004::"))
        self.assertIn("100%25 sure.md", notes[0])
        self.assertIn("no%0Awhere.md", notes[1])
        self.assertTrue(any(l.startswith("::warning ") for l in proc.stdout.splitlines()))

    def test_github_paths_include_the_root(self):
        root = self.tree({"pkg/README.md": "[x](gone.md)\n"})
        proc = run_cli("--root", "pkg", "--kind", "library", "--format", "github", cwd=root)
        self.assertIn("::error file=pkg/README.md,line=1,title=RW004::", proc.stdout)

    def test_json_shape(self):
        root = self.tree({"README.md": "# X\n\n## Install\n\n[x](gone.md)\n"})
        proc = run_cli("--root", root, "--kind", "library", "--format", "json")
        data = json.loads(proc.stdout)
        self.assertEqual(list(data), ["tool", "version", "target", "kinds", "facts", "findings", "totals"])
        self.assertEqual(data["target"], {"root": str(root), "readme": "README.md", "stdin": False})
        self.assertEqual(list(data["facts"]), ["words", "lines", "pictures", "badges", "install_line", "code_blocks"])
        self.assertEqual(set(data["findings"][0]), {"id", "severity", "path", "line", "message", "fix"})
        self.assertEqual(data["totals"]["error"], 1)

    def test_stdin_resolves_from_the_logical_path(self):
        root = self.tree({"README.md": "# Top\n", "packages/x/docs/a.md": "# A\n"})
        text = "# X\n\n[a](docs/a.md) [b](docs/b.md) [up](../../README.md#top)\n"
        proc = run_cli("--root", root, "--stdin", "--readme", "packages/x/README.md", "--kind", "library",
                       "--format", "json", input=text)
        data = json.loads(proc.stdout)
        errors = [f for f in data["findings"] if f["severity"] == "error"]
        self.assertEqual([(f["id"], f["path"]) for f in errors], [("RW004", "packages/x/README.md")])
        self.assertIn("packages/x/docs/b.md", errors[0]["message"])
        self.assertTrue(data["target"]["stdin"])

    def test_ignore_in_config(self):
        result = self.check("# X\n\n## 🚀 Go\n\nText.\n", config={"ignore": ["RW105"], "words": [0, 9999]})
        self.assertNotIn("RW105", self.ids(result))

    def test_config_cannot_hide_secrets_or_outside_targets(self):
        cfg = {"ignore": ["RW013", "RW014", "RW004"], "words": [0, 9999]}
        result = self.check("# X\n\nKey %s. [a](/etc/passwd) [b](gone.md)\n" % AWS_KEY, config=cfg)
        self.assertEqual(self.ids(result, "error"), ["RW013", "RW014"])

    def test_github_format_redacts_the_root(self):
        top = self.tree().parent
        root = top / GH_TOKEN / "proj"
        root.mkdir(parents=True)
        (root / "README.md").write_text("# X\n\n[x](gone.md)\n")
        (top / "elsewhere").mkdir()
        # A root below the working folder is shown relative to it; one outside it, as given.
        for where, cwd in ((GH_TOKEN + "/proj", top), (str(root), top / "elsewhere")):
            with self.subTest(where=cwd.name):
                proc = run_cli("--root", where, "--kind", "library", "--format", "github", cwd=cwd)
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertNotIn(GH_TOKEN, proc.stdout)
                self.assertIn("ghp_****", proc.stdout)


class Cli(Base):
    def test_help(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--stdin", proc.stdout)
        # The root confines every read but one: a config file the caller names by its full path.
        self.assertIn("except a config file you name by full path", " ".join(proc.stdout.split()))

    def test_usage_errors_are_redacted_too(self):
        for args in (("--format", GH_TOKEN), ("--bogus=" + GH_TOKEN,), ("--kind",)):
            with self.subTest(args=args[0][:8]):
                proc = run_cli(*args)
                self.assertEqual(proc.returncode, 2)
                self.assertNotIn(GH_TOKEN, proc.stderr)
                self.assertIn("check_readme.py: error:", proc.stderr)
        self.assertIn("ghp_****", run_cli("--format", GH_TOKEN).stderr)

    def test_exit_codes(self):
        root = self.tree({"ok.md": "# X\n\n## Install\n\nIt is simple.\n", "bad.md": "[x](gone.md)\n"})
        common = ("--root", root, "--kind", "library", "--config", write_json(root.parent / "c.json", {}))
        self.assertEqual(run_cli(*common, "--readme", "ok.md").returncode, 0)
        self.assertEqual(run_cli(*common, "--readme", "ok.md", "--strict").returncode, 1)
        self.assertEqual(run_cli(*common, "--readme", "bad.md").returncode, 1)
        self.assertEqual(run_cli(*common, "--readme", "missing.md").returncode, 1)

    def test_bad_usage_exits_2(self):
        root = self.tree({"README.md": "# X\n"})
        (root / "bad.json").write_text("{not json")
        for args in (("--root", root / "nope"), ("--root", root, "--kind", "gadget"),
                     ("--root", root, "--config", root / "bad.json"), ("--root", root, "--readme", "../x.md"),
                     ("--root", root, "--format", "xml"), ("--root", root, "--config", root / "none.json")):
            with self.subTest(args=args):
                self.assertEqual(run_cli(*args).returncode, 2)

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "permissions do not stop this user reading")
    def test_unreadable_readme_exits_2(self):
        root = self.tree({"README.md": "# X\n"})
        (root / "README.md").chmod(0)
        self.addCleanup((root / "README.md").chmod, 0o644)
        self.assertEqual(run_cli("--root", root, "--kind", "library").returncode, 2)

    def test_relative_config_is_read_from_the_root(self):
        root = self.tree({"README.md": "# X\n\n## Install\n\n[x](gone.md)\n", "cfg/c.json": '{"ignore": ["RW004"]}'})
        (root.parent / "outside.json").write_text("{}")
        elsewhere = root.parent
        self.assertEqual(run_cli("--root", root, "--kind", "library", "--config", "cfg/c.json", cwd=elsewhere).returncode, 0)
        proc = run_cli("--root", root, "--kind", "library", "--config", "../outside.json", cwd=root)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("leads outside the root", proc.stderr)
        self.assertEqual(run_cli("--root", root, "--kind", "library", "--config", root.parent / "outside.json").returncode, 1)
        (root.parent / "big.json").write_text('{"ignore": []}' + " " * (2 * 1024 * 1024))
        proc = run_cli("--root", root, "--config", root.parent / "big.json")
        self.assertEqual(proc.returncode, 2)

    def test_bad_config_values(self):
        root = self.tree()
        for cfg in ({"words": [10]}, {"kind": ["gadget"]}, {"ignore": "RW101"}):
            with self.subTest(cfg=cfg), self.assertRaises(check_readme.UsageError):
                check_readme.check(str(root), text="# X\n", config=cfg)

    def test_no_config_skips_the_project_config(self):
        root = self.tree({"README.md": "# X\n\n## Install\n\n[x](gone.md)\n",
                          ".readme-workshop.json": '{"ignore": ["RW004"]}'})
        self.assertEqual(run_cli("--root", root, "--kind", "library").returncode, 0)
        proc = run_cli("--root", root, "--kind", "library", "--no-config")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("RW004", proc.stdout)
        self.assertEqual(run_cli("--root", root, "--no-config", "--config", root / ".readme-workshop.json").returncode, 2)

    def test_stdin_is_capped_at_the_readme_limit(self):
        root = self.tree()
        proc = run_cli("--root", root, "--stdin", "--kind", "library", input="a" * (check_readme.MAX_README + 1))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("8 MB", proc.stderr)
        for size, code in ((1000, 1), (1001, 2)):
            with self.subTest(size=size), mock.patch.object(check_readme, "MAX_README", 1000), \
                    mock.patch("sys.stdin", io.TextIOWrapper(io.BytesIO(b"[x](gone.md)\n".ljust(size, b"a")))), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(check_readme.main(["--root", str(root), "--stdin", "--kind", "library"]), code)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes need POSIX")
    def test_config_must_be_a_regular_file(self):
        root = self.tree({"README.md": "# X\n"})
        os.mkfifo(root.parent / "config.json")
        for config in (root.parent / "config.json", root):
            with self.subTest(config=config.name):
                proc = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--config", str(config)],
                                      capture_output=True, text=True, timeout=20)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("cannot read the config", proc.stderr)


class Bytecode(Base):
    def test_entry_points_write_nothing_beside_themselves(self):
        # The skill may be installed inside the project it reads; running it must not add files there.
        copy = self.tree().parent / "skill"
        shutil.copytree(SCRIPTS, copy / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        project = self.tree({"README.md": "# X\n\n[x](gone.md)\n", "pyproject.toml": "[project]\nname = 'x'\n"})
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        for script, extra in (("discover.py", ()), ("check_readme.py", ("--kind", "library"))):
            for flags in ((), ("-I", "-B")):
                with self.subTest(script=script, flags=flags):
                    proc = subprocess.run([sys.executable, *flags, str(copy / "scripts" / script), "--root",
                                           str(project), *extra], capture_output=True, text=True, env=env, timeout=120)
                    self.assertIn(proc.returncode, (0, 1), proc.stderr)
                    self.assertEqual(sorted(p.name for p in (copy / "scripts").iterdir()),
                                     sorted(p.name for p in SCRIPTS.iterdir() if p.name != "__pycache__"))
                    self.assertEqual(sorted(p.name for p in project.iterdir()), ["README.md", "pyproject.toml"])


@unittest.skipIf(os.name == "nt", "the Action's step runs in bash; on Windows the bash found first is WSL's launcher. CI's action job runs the real Action.")
class Action(Base):
    """action.yml: the inputs reach the checker safely."""

    ACTION = HERE.parent / "action.yml"

    def step(self):
        import formats
        data, certain = formats.read_yaml(self.ACTION.read_text(encoding="utf-8"))
        self.assertTrue(certain)
        return data, next(s for s in data["runs"]["steps"] if "run" in s)

    def run_action(self, cwd, python_in_workspace=False, **inputs):
        bin_dir = self.tree().parent / "bin"
        bin_dir.mkdir()
        os.symlink(sys.executable, bin_dir / "python3")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "RW_", "GITHUB_"))}
        env.update(PATH="%s%s%s" % (bin_dir, os.pathsep, env.get("PATH", "")), RW_SCRIPT=str(SCRIPT),
                   RW_README="README.md", RW_ROOT=".", RW_STRICT="false", RW_KIND="library", RW_USE_CONFIG="true")
        if python_in_workspace:
            env["GITHUB_WORKSPACE"] = str(bin_dir.parent)
        env.update(inputs)
        return subprocess.run(["bash", "-c", self.step()[1]["run"]], cwd=cwd, env=env, capture_output=True,
                              text=True, timeout=120)

    def test_use_config_input(self):
        data, step = self.step()
        self.assertEqual(data["inputs"]["use-config"]["default"], "true")
        self.assertEqual(step["env"]["RW_USE_CONFIG"], "${{ inputs.use-config }}")
        root = self.tree({"README.md": "# X\n\n[x](gone.md)\n", ".readme-workshop.json": '{"ignore": ["RW004"]}'})
        self.assertEqual(self.run_action(root).returncode, 0)
        proc = self.run_action(root, RW_USE_CONFIG="false")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("title=RW004", proc.stdout)

    def test_values_that_start_with_a_dash(self):
        top = self.tree().parent
        (top / "-proj").mkdir()
        (top / "-proj" / "README.md").write_text("# X\n\n[x](gone.md)\n")
        proc = self.run_action(top, RW_ROOT="-proj")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("::error file=-proj/README.md,line=3,title=RW004::", proc.stdout)

    def test_python_inside_the_checkout_and_bad_inputs_are_refused(self):
        root = self.tree({"README.md": "# X\n"})
        proc = self.run_action(root, python_in_workspace=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("inside the checkout", proc.stdout)
        proc = self.run_action(root, RW_USE_CONFIG="flase")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("use-config must be", proc.stdout)
        # A python3 outside the checkout that is a link to a program inside it is the program inside it.
        top = root.parent
        (top / "inside").mkdir()
        (top / "inside" / "python3").write_text('#!/bin/sh\nexec "%s" "$@"\n' % sys.executable)
        (top / "inside" / "python3").chmod(0o755)
        (top / "linked").mkdir()
        symlink("../inside/python3", top / "linked" / "python3")
        env_path = "%s%s%s" % (top / "linked", os.pathsep, os.environ.get("PATH", ""))
        proc = self.run_action(root, python_in_workspace=False, GITHUB_WORKSPACE=str(top / "inside"), PATH=env_path)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("inside the checkout", proc.stdout)
        for value in ("TRUE", "yes", "1", ""):  # a mistyped strict must not quietly turn the gate off
            with self.subTest(strict=value):
                proc = self.run_action(root, RW_STRICT=value)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("strict must be", proc.stdout)

    def test_the_ci_failures_fail_for_their_findings(self):
        # What the workflow's last step asserts: exit 1 and the rule each failing run is there for.
        for inputs, rule in (({"RW_ROOT": "tests/fixtures/check/hello-action", "RW_README": "README-bad.md"}, "RW009"),
                             ({"RW_ROOT": "tests/fixtures/check/good", "RW_USE_CONFIG": "false", "RW_STRICT": "true"},
                              "RW101")):
            with self.subTest(rule=rule):
                proc = self.run_action(HERE.parent, RW_KIND="", **inputs)
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertIn("title=%s::" % rule, proc.stdout)
        import formats
        workflow, _ = formats.read_yaml((HERE.parent / ".github" / "workflows" / "test.yml").read_text())
        last = workflow["jobs"]["action"]["steps"][-1]["run"]
        self.assertIn('expect "RW009" RW_ROOT=tests/fixtures/check/hello-action RW_README=README-bad.md', last)
        self.assertIn('expect "RW101" RW_ROOT=tests/fixtures/check/good RW_USE_CONFIG=false RW_STRICT=true', last)

    def test_ci_runs_this_action(self):
        import formats
        workflow, certain = formats.read_yaml((HERE.parent / ".github" / "workflows" / "test.yml").read_text())
        self.assertTrue(certain)
        uses = [s.get("uses") for job in workflow["jobs"].values() for s in job["steps"]]
        self.assertGreaterEqual(uses.count("./"), 3)

    def test_python_probe_ignores_the_environment(self):
        top = self.tree({"README.md": "# X\n"}).parent
        evil = top / "evil"
        evil.mkdir()
        marker = top / "RAN"
        (evil / "sitecustomize.py").write_text("open(%r, 'w').write('ran')\n" % str(marker))
        self.run_action(top / "proj", PYTHONPATH=str(evil))
        self.assertFalse(marker.exists(), "the Python probe ran code from PYTHONPATH")


class OpenSpy:
    """Records the full path of every file or folder opened, by open() or os.open() (dir_fd included)."""

    def __init__(self):
        self.paths, self._fds = [], {}
        self._open, self._os_open, self._dup = builtins.open, os.open, os.dup

    def os_open(self, path, flags, mode=0o777, *, dir_fd=None):
        fd = self._os_open(path, flags, mode, dir_fd=dir_fd)
        full = os.path.normpath(os.path.join(self._fds[dir_fd], path)) if dir_fd in self._fds else os.path.realpath(path)
        self._fds[fd] = full
        self.paths.append(full)
        return fd

    def dup(self, fd):
        new = self._dup(fd)
        if fd in self._fds:
            self._fds[new] = self._fds[fd]
        return new

    def open(self, file, *args, **kw):
        if isinstance(file, (str, bytes, os.PathLike)):
            self.paths.append(os.path.realpath(file))
        return self._open(file, *args, **kw)

    def __enter__(self):
        self._patches = [mock.patch("builtins.open", self.open), mock.patch("io.open", self.open),
                         mock.patch("os.open", self.os_open), mock.patch("os.dup", self.dup)]
        for patch in self._patches:
            patch.start()
        return self

    def __exit__(self, *exc):
        for patch in self._patches:
            patch.stop()


def symlink(target, link):
    try:
        os.symlink(target, link, target_is_directory=Path(target).is_dir())
    except (OSError, NotImplementedError) as exc:
        raise unittest.SkipTest("symlinks are not available here: %s" % exc)


def write_json(path, data):
    path.write_text(json.dumps(data))
    return path


def run_cli(*args, input=None, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], input=input, capture_output=True,
                          text=True, encoding="utf-8", cwd=cwd, timeout=120)


if __name__ == "__main__":
    unittest.main()
