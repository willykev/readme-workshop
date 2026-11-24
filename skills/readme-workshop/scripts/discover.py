#!/usr/bin/env python3
"""Read-only project scanner for the readme-workshop skill.

Walks a project tree without following symlinks, reads manifests and source
files as text, and reports what kind of project it is and what it offers
(entry points, commands, API, tools, routes, shortcuts, environment
variables), each with the path and line that shows it. It never imports or
runs project code; the only programs it starts are a few read-only git
commands.
"""

from __future__ import annotations

import bisect
import configparser
import json
import os
import posixpath
import re
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, deque

# The sibling modules come from this folder and nowhere else, and no bytecode is
# written beside them: the skill may be installed inside the project it reads.
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if sys.path[:1] != [HERE]:
    sys.path.insert(0, HERE)
import formats  # noqa: E402
import safety  # noqa: E402
from safety import is_secret_path  # noqa: E402,F401  (part of this module's interface)

VERSION = "0.1.3"

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "target", "out", ".venv", "venv", "env",
    "__pycache__", ".tox", ".mypy_cache", ".pytest_cache", ".next", ".nuxt", "coverage", ".gradle",
    ".idea", ".vscode-test", "site-packages", "bower_components", "Pods", "DerivedData",
}
HIDDEN_ALLOW = {
    ".github", ".claude-plugin", ".agents", ".claude", ".codex-plugin", ".cursor-plugin",
    ".antigravity-plugin", ".grok-plugin", ".pre-commit-hooks.yaml", ".pre-commit-config.yaml",
    ".devcontainer", ".vscode", ".env.example", ".env.sample",
}
# Inside these hidden folders only the named subfolders are walked.
HIDDEN_ONLY = {".claude": {"skills", "commands"}, ".agents": {"skills"}}
IMAGE_EXT = {".png", ".gif", ".jpg", ".jpeg", ".webp", ".svg", ".avif", ".ico", ".bmp", ".tif", ".tiff", ".heic", ".jxl"}
BINARY_EXT = set(
    ".exe .dll .so .dylib .a .o .obj .lib .class .jar .war .pyc .pyo .whl .zip .gz .tgz .bz2 .xz .zst "
    ".7z .rar .tar .pdf .mp3 .mp4 .mov .avi .mkv .webm .wav .flac .ogg .ttf .otf .woff .woff2 .eot .bin "
    ".dat .db .sqlite .sqlite3 .wasm .node .deb .rpm .dmg .iso .img .psd .xcf .blend .pkg .apk .ipa".split()
)
LANGS = {
    ".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript", ".cts": "TypeScript",
    ".rs": "Rust", ".go": "Go", ".c": "C", ".cc": "C++", ".cpp": "C++", ".cxx": "C++", ".hpp": "C++",
    ".hh": "C++", ".h": "C", ".qml": "QML", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".swift": "Swift", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".lua": "Lua", ".sh": "Shell",
    ".bash": "Shell", ".zsh": "Shell", ".fish": "Shell", ".ex": "Elixir", ".exs": "Elixir", ".dart": "Dart",
    ".scala": "Scala", ".zig": "Zig", ".nix": "Nix", ".vue": "Vue", ".svelte": "Svelte", ".html": "HTML",
    ".css": "CSS", ".scss": "CSS", ".m": "Objective-C", ".mm": "Objective-C", ".jl": "Julia",
    ".hs": "Haskell", ".ml": "OCaml", ".pl": "Perl", ".r": "R", ".ps1": "PowerShell",
}
SHEBANG_LANGS = {"python": "Python", "bash": "Shell", "sh": "Shell", "zsh": "Shell", "node": "JavaScript", "deno": "TypeScript", "ruby": "Ruby", "perl": "Perl"}
STYLE = {"Python": "hash", "Shell": "sh", "Ruby": "hash", "Rust": "rust", "Go": "go", "Lua": "lua"}
MANIFEST_NAMES = {
    "pyproject.toml": "pyproject", "setup.cfg": "setup.cfg", "setup.py": "setup.py", "package.json": "package.json",
    "Cargo.toml": "Cargo.toml", "go.mod": "go.mod", "PKGBUILD": "PKGBUILD", ".SRCINFO": ".SRCINFO",
    "Gemfile": "Gemfile", "composer.json": "composer.json", "pom.xml": "pom.xml", "build.gradle": "build.gradle",
    "build.gradle.kts": "build.gradle", "CMakeLists.txt": "CMakeLists.txt", "meson.build": "meson.build",
    "Makefile": "Makefile", "makefile": "Makefile", "GNUmakefile": "Makefile", "Dockerfile": "Dockerfile",
    "Containerfile": "Dockerfile", "compose.yaml": "compose", "compose.yml": "compose",
    "docker-compose.yaml": "compose", "docker-compose.yml": "compose", "action.yml": "action.yml",
    "action.yaml": "action.yml", "SKILL.md": "SKILL.md", "plugin.json": "plugin.json",
    "marketplace.json": "marketplace.json", "gemini-extension.json": "gemini-extension.json",
    "manifest.json": "manifest.json", "flake.nix": "flake.nix", "Package.swift": "Package.swift",
    "deno.json": "deno.json", "deno.jsonc": "deno.json", "pubspec.yaml": "pubspec.yaml", "mix.exs": "mix.exs",
}
MANIFEST_SUFFIXES = {".gemspec": "*.gemspec", ".pro": "*.pro", ".csproj": "*.csproj"}
TEST_DIRS = {"tests", "test", "__tests__", "spec", "testdata", "testing"}
EXAMPLE_DIRS = {"examples", "example", "samples", "sample"}
DEV_DIRS = {"scripts", "tools", "research", "benchmarks", "bench", "hack", "ci", "docs", ".github", "dev", "bin"}
# Helper scripts at any depth (a skill's scripts/, a package's tools/) are not the project's own CLI or API.
HELPER_DIRS = {"scripts", "tools", "research", "benchmarks", "bench", "hack"}
TEST_FILE_RE = re.compile(r"(^test_.*\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$|_spec\.rb$|Tests?\.(java|kt|swift|cs)$)")
SYSTEM_ENV = {"HOME", "PATH", "USER", "USERNAME", "PWD", "SHELL", "TERM", "LANG", "LC_ALL", "TMPDIR", "TEMP",
              "TMP", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "DISPLAY", "EDITOR", "VISUAL", "NO_COLOR", "CI"}
KIND_ORDER = ["app", "terminal", "service", "library", "extension", "automation"]
CONFIDENCE = {"low": 0, "medium": 1, "high": 2}
SURFACE_KEYS = ["cli", "api", "tools", "commands", "skills", "hooks", "action", "routes", "env", "shortcuts", "config"]
SAMPLE_LIMIT = 100  # skipped entries kept per reason; the report shows the first 100
ENTRY_FACTOR = 10  # directory entries examined, per file allowed by --max-files
TEXT_BUDGET = 64 * 1024 * 1024  # bytes of file text held in memory across the scan
IMAGE_HEAD = 64 * 1024  # bytes read to find an image's size
CALL_LIMIT = 300  # registrations read per pattern per file; bounds the work on hostile input (past it: a gap)
SIGNAL_LIMIT = 25
# This skill, as a host installs it into a project: not part of the project it reads.
OWN_SKILL = "readme-workshop"
OWN_SKILL_DIRS = {"skills/" + OWN_SKILL, ".claude/skills/" + OWN_SKILL, ".agents/skills/" + OWN_SKILL}

STR_RE = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|`([^`$\\]*)`')
TOKENS = {
    "c": re.compile(r'//[^\n]*|/\*.*?\*/|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`', re.S),
    "hash": re.compile(r'"""(?:[^\\]|\\.)*?"""|\'\'\'(?:[^\\]|\\.)*?\'\'\'|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|#[^\n]*', re.S),
    "sh": re.compile(r'"(?:[^"\\]|\\.)*"|\'[^\']*\'|(?<!\S)#[^\n]*', re.S),
    "lua": re.compile(r'--\[(=*)\[.*?\]\1\]|--[^\n]*|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'', re.S),
    "rust": re.compile(r'//[^\n]*|/\*.*?\*/|"(?:[^"\\]|\\.)*"|\'(?:\\.[^\']{0,8}|[^\'\\\n])\'', re.S),
    "go": re.compile(r'//[^\n]*|/\*.*?\*/|"(?:[^"\\\n]|\\.)*"|\'(?:\\.[^\']{0,8}|[^\'\\\n])\'|`[^`]*`', re.S),
}


# ---------------------------------------------------------------- small helpers


_NOT_NEWLINE = re.compile(r"[^\n]")


def strip_comments(text, style):
    """Blank out comments and multi-line strings (templates, docstrings, generated
    code) with spaces, so offsets and line numbers match the original text."""
    def keep(m):
        t = m.group(0)
        if t[0] not in "\"'`":
            return _NOT_NEWLINE.sub(" ", t)
        if "\n" not in t:
            return t
        q = 3 if t[:3] in ('"""', "\'\'\'") else 1
        return t[:q] + _NOT_NEWLINE.sub(" ", t[q:-q]) + t[-q:]
    return TOKENS.get(style, TOKENS["c"]).sub(keep, text)


def lits(text):
    """Contents of the string literals in text, in order."""
    return [next(g for g in m.groups() if g is not None) for m in STR_RE.finditer(text)]


def lit_at(text):
    """The string literal that text starts with (after spaces), or None."""
    m = STR_RE.match(text.lstrip(" \t\n("))
    return None if m is None else next(g for g in m.groups() if g is not None)


def kwarg(args, name):
    """Literal value of `name=` or `name:` inside call arguments, or None."""
    m = re.search(r"\b" + name + r"\s*[:=]\s*", args)
    return lit_at(args[m.end():]) if m else None


_BRACKETS = re.compile(r"[()\[\]{}\"'`\n]")
_PAIRS = {"(": ")", "{": "}", "[": "]"}


def balanced(code, start, limit=4000):
    """code from the bracket at start to its partner (or to the limit), skipping strings."""
    open_ch, close_ch = code[start], _PAIRS[code[start]]
    depth, quote, end = 0, None, min(len(code), start + limit)
    for m in _BRACKETS.finditer(code, start, end):
        ch, at = m.group(), m.start()
        if quote:
            if ch == "\n" and quote != "`":
                quote = None
            elif ch == quote:
                k = at - 1
                while k > start and code[k] == "\\":
                    k -= 1
                if (at - 1 - k) % 2 == 0:
                    quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return code[start:at + 1]
    return code[start:end]


def find_line(text, pattern, after=None, default=1):
    """1-based line of the first match of pattern (after the `after` match), or default."""
    pos = 0
    if after:
        m = re.search(after, text, re.M)
        pos = m.end() if m else 0
    m = re.compile(pattern, re.M).search(text, pos)
    return text.count("\n", 0, m.start()) + 1 if m else default


def kebab(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name).replace("_", "-").lower()


def best_flag(names):
    flags = [n for n in names if n.startswith("-")]
    longs = [n for n in flags if n.startswith("--")]
    return (longs or flags or [None])[0]


def image_size(path, root=None):
    """(width, height) from a PNG, GIF, JPEG or WebP header, else (None, None).

    Reads at most IMAGE_HEAD bytes, from a regular file only. root is a
    safety.Tree (or a folder) the path is relative to.
    """
    if isinstance(root, safety.Tree):
        head = root.read_bytes(path, IMAGE_HEAD, follow=False)
    else:
        head = safety.read_regular(path, IMAGE_HEAD, root)
    try:
        return header_size(head or b"")
    except struct.error:
        return None, None


def header_size(head):
    if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
        return struct.unpack(">II", head[16:24])
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", head[6:10])
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        kind = head[12:16]
        if kind == b"VP8X":
            return 1 + int.from_bytes(head[24:27], "little"), 1 + int.from_bytes(head[27:30], "little")
        if kind == b"VP8 ":
            return int.from_bytes(head[26:28], "little") & 0x3FFF, int.from_bytes(head[28:30], "little") & 0x3FFF
        if kind == b"VP8L":
            bits = int.from_bytes(head[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if head[:2] == b"\xff\xd8":
        return jpeg_size(head)
    return None, None


def jpeg_size(head):
    """Walk a JPEG's marker segments, within the bytes read, to its frame header."""
    pos = 2
    for _ in range(500):
        pos = head.find(b"\xff", pos)
        if pos < 0:
            break
        while pos < len(head) and head[pos] == 0xFF:  # fill bytes before a marker
            pos += 1
        if pos >= len(head):
            break
        marker = head[pos]
        pos += 1
        if marker == 0x01 or 0xD0 <= marker <= 0xD9:  # markers without a length
            continue
        if pos + 2 > len(head):
            break
        length = struct.unpack(">H", head[pos:pos + 2])[0]
        if length < 2:  # the length counts its own two bytes; less is a broken file
            break
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if pos + 7 > len(head):
                break
            h, w = struct.unpack(">HH", head[pos + 3:pos + 7])
            return w, h
        pos += length
    return None, None


def entry_kind(entry):
    """(kind, size) of a directory entry, never following a symlink."""
    try:
        if entry.is_symlink():
            return "symlink", 0
        if entry.is_dir(follow_symlinks=False):
            return "dir", 0
        if entry.is_file(follow_symlinks=False):
            return "file", entry.stat(follow_symlinks=False).st_size
    except OSError:
        pass
    return "other", 0


class Source:
    """A source file's text, its comment-free code, and offset-to-line lookup."""

    scanner = None  # the Scanner that read it, which records what calls() leaves unread

    def __init__(self, path, text, lang):
        self.path, self.text, self.lang = path, text, lang
        self.code = strip_comments(text, STYLE.get(lang, "c"))
        self._breaks = None
        self._lines = None

    def line(self, offset):
        if self._breaks is None:
            self._breaks = [m.start() for m in re.finditer("\n", self.code)]
        return bisect.bisect_left(self._breaks, offset) + 1

    def raw_line(self, number):
        if self._lines is None:
            self._lines = self.text.split("\n")
        return self._lines[number - 1] if 0 < number <= len(self._lines) else ""


# ---------------------------------------------------------------- the scanner


class Scanner:
    def __init__(self, root, max_files, max_bytes):
        # root is a folder, or a safety.Tree already pinned (check_readme's), which the scan reads through.
        self.own_tree = not isinstance(root, safety.Tree)
        self.tree = safety.Tree(root) if self.own_tree else root
        self.root = self.tree.abs
        try:
            with self.tree.scandir(""):  # raises PermissionError early
                pass
        except BaseException:
            self.close()
            raise
        self.max_files, self.max_bytes = max_files, max_bytes
        self.files, self.sizes, self.langs = [], {}, {}
        self.skipped, self.skip_count, self.skip_reasons, self.images = [], 0, Counter(), []
        self.truncated = False
        self._text, self._src, self._head = {}, {}, {}
        self.text_bytes = 0
        self.manifests, self.parsed = [], {}
        self.kinds, self.entry_points, self.channels, self.platforms = {}, [], [], []
        self.surfaces = {k: [] for k in SURFACE_KEYS}
        self.surfaces["action"] = None
        self.signals = {k: [] for k in ("network", "storage", "telemetry", "account")}
        self.flags = Counter()
        self.focus = None
        self.declared = set()
        self.history = {"git": False, "commits": None, "tags": [], "last_readme_commit": None,
                        "since": None, "since_error": None, "skipped_reason": None, "changed": [], "untracked": []}
        self.mcp_instances, self.mcp_pending = set(), []
        self._ships_self = None

    def close(self):
        if self.own_tree:
            self.tree.close()

    # Walking ---------------------------------------------------------------

    def skip(self, path, reason, line=None, **extra):
        """Count a path left unread; the first SAMPLE_LIMIT of each reason are kept as a sample."""
        self.skip_count += 1
        self.skip_reasons[reason] += 1
        if self.skip_reasons[reason] <= SAMPLE_LIMIT:
            entry = {"path": path, "reason": reason}
            if line is not None:
                entry["line"] = line
            entry.update(extra)
            self.skipped.append(entry)

    def walk(self):
        seen = 0
        budget = self.max_files * ENTRY_FACTOR  # directory entries examined, files and folders alike
        queue = deque([""])
        while queue and not self.truncated:
            rel_dir = queue.popleft()
            entries = self.list_dir(rel_dir, budget)
            if entries is None:
                self.skip(rel_dir, "dir")
                continue
            if len(entries) > budget:
                self.truncated = True
                self.skip(rel_dir or ".", "cap")
                entries = entries[:budget]
            budget -= len(entries)
            only = HIDDEN_ONLY.get(rel_dir)
            files, dirs = [], []
            for name, kind, size in entries:
                rel = f"{rel_dir}/{name}" if rel_dir else name
                if only is not None and name not in only:
                    continue
                if kind == "symlink":
                    self.skip(rel, "symlink")
                elif kind == "dir":
                    if name in SKIP_DIRS or (name.startswith(".") and name not in HIDDEN_ALLOW):
                        if name != ".git":
                            self.skip(rel, "dir")
                    elif is_secret_path(rel):
                        self.skip(rel, "secret")
                    elif rel in OWN_SKILL_DIRS and self.installed_copy(rel):
                        self.skip(rel, "installed-skill")
                    else:
                        dirs.append(rel)
                elif kind == "file":
                    if is_secret_path(rel):
                        self.skip(rel, "secret")
                    elif not name.startswith(".") or name in HIDDEN_ALLOW or name == ".SRCINFO":
                        files.append((name, rel, size))
            files.sort(key=lambda f: (f[0] not in MANIFEST_NAMES, f[0]))
            for name, rel, size in files:
                if seen >= self.max_files:
                    self.truncated = True
                    self.skip(rel, "cap")
                    break
                seen += 1
                self.consider(rel, name, size)
            queue.extend(dirs)

    def list_dir(self, rel_dir, limit):
        """Up to limit + 1 entries of a folder as (name, kind, size), sorted; None if it cannot be read.

        kind is symlink, dir, file or other. The folder is opened without
        following any symlink below the root (safety.Tree.scandir).
        """
        out = []
        try:
            with self.tree.scandir(rel_dir) as it:
                for entry in it:
                    out.append((entry.name, *entry_kind(entry)))
                    if len(out) > limit:
                        break
        except OSError:
            return None
        return sorted(out)

    def installed_copy(self, rel):
        """True when rel holds an installed copy of this skill, which the project does not ship itself."""
        data, _, _ = formats.frontmatter(safety.decode_text(self.read_bytes(rel + "/SKILL.md", 65537), 65536) or "")
        if not isinstance(data, dict) or data.get("name") != OWN_SKILL:
            return False
        if rel.startswith("."):  # .claude/skills or .agents/skills: where a host installs skills
            return True
        if self._ships_self is None:
            self._ships_self = OWN_SKILL in self.own_names()
        return not self._ships_self

    def own_names(self):
        """The names the project's root manifests give it."""
        names = set()
        for rel in ("plugin.json", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "package.json",
                    "gemini-extension.json", "pyproject.toml"):
            text = safety.decode_text(self.read_bytes(rel, 1 << 20), (1 << 20) - 1) or ""
            data = formats.parse_toml(text) if rel.endswith(".toml") else formats.parse_json(text)
            data = (data or {}).get("project") if rel.endswith(".toml") and isinstance(data, dict) else data
            if isinstance(data, dict) and isinstance(data.get("name"), str):
                names.add(data["name"])
        return names

    @staticmethod
    def is_secret(name):
        return is_secret_path(name)

    def consider(self, rel, name, size):
        ext = os.path.splitext(name)[1].lower()
        if ext in IMAGE_EXT:
            # Only a bounded header is read, so pictures of any size are measured.
            width, height = image_size(rel, self.root) if ext != ".svg" else (None, None)
            self.images.append({"path": rel, "bytes": size, "width": width, "height": height})
            self.files.append(rel)
            return
        if ext in BINARY_EXT:
            return self.skip(rel, "binary")
        if size > self.max_bytes:
            return self.skip(rel, "too-large")
        head = self.read_bytes(rel, 8192)
        if head is None:
            return self.skip(rel, "unreadable")
        if b"\0" in head:
            return self.skip(rel, "binary")
        if size <= 8192:
            self._head[rel] = head
        lang = LANGS.get(ext)
        if lang is None and not ext and head.startswith(b"#!"):
            first = head.split(b"\n", 1)[0].decode("latin-1")
            words = re.findall(r"[a-z]+", first.rsplit("/", 1)[-1])
            lang = next((SHEBANG_LANGS[w] for w in words if w in SHEBANG_LANGS), None)
        self.langs[rel] = lang
        self.files.append(rel)
        self.sizes[rel] = size

    def read_bytes(self, rel, limit):
        """Up to limit bytes of a regular file below the root, or None (see safety.Tree.read_bytes)."""
        return self.tree.read_bytes(rel, limit, follow=False)

    def read(self, rel):
        """Text of a scanned (not skipped) file, or None."""
        if rel in self._text:
            return self._text[rel]
        text = None
        if rel in self.sizes:
            data = self._head.pop(rel, None)
            if data is None:
                data = self.read_bytes(rel, self.max_bytes)
                if data is None:
                    self.skip(rel, "unreadable")
            if data is not None and self.text_bytes + len(data) > TEXT_BUDGET:
                self.truncated = True
                self.skip(rel, "cap")
                data = None
            if data is not None:
                self.text_bytes += len(data)
                text = data.decode("utf-8", "replace").lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
        self._text[rel] = text
        return text

    def source(self, rel):
        if rel not in self._src:
            text = self.read(rel)
            self._src[rel] = None if text is None else Source(rel, text, self.langs.get(rel))
            if self._src[rel] is not None:
                self._src[rel].scanner = self
        return self._src[rel]

    # Path classes ----------------------------------------------------------

    @staticmethod
    def is_test(rel):
        parts = rel.split("/")
        return any(p in TEST_DIRS for p in parts[:-1]) or bool(TEST_FILE_RE.search(parts[-1]))

    @staticmethod
    def is_example(rel):
        return any(p in EXAMPLE_DIRS for p in rel.split("/")[:-1])

    def is_dev(self, rel):
        # bin/ holds build helpers unless a manifest installs a file from it.
        return "/" in rel and rel.split("/", 1)[0] in DEV_DIRS and rel not in self.declared

    def product(self, rel):
        """True for files that describe the shipped project, not tests, examples or tooling."""
        return not (self.is_test(rel) or self.is_example(rel) or self.is_dev(rel))

    def code_files(self, *langs):
        return [f for f in self.files if self.langs.get(f) in langs and self.product(f)]

    def named(self, *names):
        return [f for f in self.files if f.rsplit("/", 1)[-1] in names and self.product(f)]

    # Recording -------------------------------------------------------------

    def kind(self, kind, subkind, confidence, path, line, why):
        entry = self.kinds.setdefault((kind, subkind), {"confidence": confidence, "evidence": []})
        if CONFIDENCE[confidence] > CONFIDENCE[entry["confidence"]]:
            entry["confidence"] = confidence
        if len(entry["evidence"]) < 5 and not any(e["path"] == path and e["why"] == why for e in entry["evidence"]):
            entry["evidence"].append({"path": path, "line": line or 1, "why": why})

    def entry(self, name, path, line, via, cli=True):
        if name and not any(e["name"] == name and e["via"] == via for e in self.entry_points):
            self.entry_points.append({"name": name, "path": path, "line": line or 1, "via": via, "_cli": cli})

    def channel(self, channel, name, path, line):
        if not any(c["channel"] == channel for c in self.channels):
            self.channels.append({"channel": channel, "name": name, "evidence": {"path": path, "line": line or 1}})

    def platform(self, platform, path, line):
        if not any(p["platform"] == platform for p in self.platforms):
            self.platforms.append({"platform": platform, "evidence": {"path": path, "line": line or 1}})

    # (category, name, kind, method) -> the item recorded under it, for the categories kept unique.
    _recorded = None

    def surface(self, category, item, manifest=False):
        name = item.get("name") or item.get("event") or item.get("route") or item.get("keys") or ""
        if not name or name.lstrip("-").startswith("_"):
            return
        path = item.get("path", "")
        if category in ("cli", "api") and any(p in HELPER_DIRS for p in path.split("/")[:-1]):
            return
        if self.focus is not None and not manifest and path not in self.focus:
            # Kept until the kinds are settled, then dropped by focus_surfaces: with --since the
            # project is still the same kind of project.
            item["_unfocused"] = True
        if category in ("env", "skills", "commands", "cli", "api", "tools"):
            if self._recorded is None:
                self._recorded = {}
            key = (category, name, item.get("kind"), item.get("method"))
            known = self._recorded.get(key)
            if known is not None:
                if known.get("_unfocused") and not item.get("_unfocused"):
                    known.clear()
                    known.update(item)
                return
            self._recorded[key] = item
        self.surfaces[category].append(item)

    def dynamic(self, path, line, what):
        if self.focus is None or path in self.focus:
            self.skip(path, "dynamic", line, what=what)

    def malformed(self, path, what):
        """Note a manifest part that has the wrong shape; the rest of the file is still read."""
        self.skip(path, "malformed", what=what)

    def capped(self, path, line, area):
        """Note that a file registers more than CALL_LIMIT names one way, and the rest were not read."""
        self.skip(path, "capped", line, area=area)

    def signal(self, category, path, line, what):
        bucket = self.signals[category]
        if len(bucket) < SIGNAL_LIMIT and not any(b["path"] == path and b["what"] == what for b in bucket):
            bucket.append({"path": path, "line": line, "what": what})

    def manifest(self, rel, mtype, **fields):
        record = {"path": rel, "type": mtype, "name": None, "version": None, "description": None,
                  "license": None, "bins": [], "scripts": {}, "homepage": None, "repository": None}
        for key, value in fields.items():
            if value not in (None, "", [], {}):
                record[key] = value
        self.manifests.append(record)
        return record

    def is_manifest(self, rel):
        return any(m["path"] == rel for m in self.manifests)


# ---------------------------------------------------------------- manifests


def _str(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _url(value):
    return _str(value.get("url")) if isinstance(value, dict) else _str(value)


def _table(s, rel, value, label):
    """value when it is a table, {} when absent; any other shape is noted as malformed and
    read as empty, so one odd field never stops the scan."""
    if value is not None and not isinstance(value, dict):
        s.malformed(rel, f"{label} is not a table")
        return {}
    return value or {}


def shell_var(text, var):
    m = re.search(r"^" + var + r"=(\([^)]*\)|'[^']*'|\"[^\"]*\"|\S+)", text, re.M)
    if not m:
        return None
    value = m.group(1)
    if value.startswith("("):
        items = lits(value) or value[1:-1].split()
        return items[0] if items else None
    value = value.strip("'\"")
    return None if "$" in value else value


def parsed_or_noted(s, rel, data, what):
    """data when a manifest parsed; otherwise {} and a note that it could not be read, which is a gap."""
    if data is None:
        s.malformed(rel, what)
        return {}
    return data


def read_pyproject(s, rel, text):
    data = s.parsed[rel] = parsed_or_noted(s, rel, formats.parse_toml(text), "is not valid TOML")
    proj = _table(s, rel, data.get("project"), "project")
    poetry = _table(s, rel, _table(s, rel, data.get("tool"), "tool").get("poetry"), "tool.poetry")
    scripts = {**_table(s, rel, poetry.get("scripts"), "tool.poetry.scripts"),
               **_table(s, rel, proj.get("scripts"), "project.scripts")}
    lic = proj.get("license") or poetry.get("license")
    lic = lic.get("text") if isinstance(lic, dict) else lic
    urls = {str(k).lower(): v for k, v in _table(s, rel, proj.get("urls"), "project.urls").items()}
    return dict(name=_str(proj.get("name") or poetry.get("name")), version=_str(proj.get("version") or poetry.get("version")),
                description=_str(proj.get("description") or poetry.get("description")), license=_str(lic),
                bins=list(scripts), homepage=_str(urls.get("homepage") or poetry.get("homepage")),
                repository=_str(urls.get("repository") or urls.get("source") or poetry.get("repository")))


def read_setup_cfg(s, rel, text):
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error:
        s.malformed(rel, "is not a valid setup.cfg")
        return {}
    meta = parser["metadata"] if parser.has_section("metadata") else {}
    entry = parser.get("options.entry_points", "console_scripts", fallback="")
    bins = re.findall(r"^[ \t]*([\w.-]+)\s*=", entry, re.M)
    return dict(name=_str(meta.get("name")), version=_str(meta.get("version")), description=_str(meta.get("description")),
                license=_str(meta.get("license")), homepage=_str(meta.get("url")), bins=bins)


def read_setup_py(s, rel, text):
    get = lambda key: (re.search(r"\b" + key + r"\s*=\s*['\"]([^'\"]+)['\"]", text) or [None, None])[1]  # noqa: E731
    block = re.search(r"console_scripts['\"]\s*:\s*\[([^\]]*)\]", text)
    bins = re.findall(r"['\"]\s*([\w.-]+)\s*=", block.group(1)) if block else []
    return dict(name=get("name"), version=get("version"), description=get("description"), license=get("license"),
                homepage=get("url"), bins=bins)


def read_package_json(s, rel, text):
    data = formats.parse_json(text)
    if not isinstance(data, dict):
        s.malformed(rel, "is not a JSON object")
        return {}
    s.parsed[rel] = data
    name = _str(data.get("name"))
    bins = data.get("bin")
    targets = [bins] if isinstance(bins, str) else list(bins.values()) if isinstance(bins, dict) else []
    s.declared.update(posixpath.normpath(posixpath.join(posixpath.dirname(rel), t)) for t in targets if isinstance(t, str))
    bins = [name.split("/")[-1]] if isinstance(bins, str) and name else list(bins) if isinstance(bins, dict) else []
    scripts = {k: v for k, v in (data.get("scripts") or {}).items() if isinstance(v, str)} if isinstance(data.get("scripts"), dict) else {}
    return dict(name=name, version=_str(data.get("version")), description=_str(data.get("description")),
                license=_str(data.get("license")), bins=bins, scripts=scripts, homepage=_str(data.get("homepage")),
                repository=_url(data.get("repository")))


def read_cargo(s, rel, text):
    data = s.parsed[rel] = parsed_or_noted(s, rel, formats.parse_toml(text), "is not valid TOML")
    pkg = _table(s, rel, data.get("package"), "package")
    base = posixpath.dirname(rel)
    targets = [b for b in data.get("bin") if isinstance(b, dict)] if isinstance(data.get("bin"), list) else []
    bins = [b["name"] for b in targets if _str(b.get("name"))]
    if _str(pkg.get("name")) and posixpath.join(base, "src/main.rs") in s.sizes and not any(
            str(b.get("path") or "").endswith("src/main.rs") for b in targets):
        bins.append(pkg["name"])
    prefix = posixpath.join(base, "src/bin/")
    bins += [f[len(prefix):-3] for f in s.files if f.startswith(prefix) and f.endswith(".rs") and "/" not in f[len(prefix):]]
    return dict(name=_str(pkg.get("name")), version=_str(pkg.get("version")), description=_str(pkg.get("description")),
                license=_str(pkg.get("license")), bins=list(dict.fromkeys(bins)), homepage=_str(pkg.get("homepage")),
                repository=_str(pkg.get("repository")))


def read_pkgbuild(s, rel, text):
    bins = re.findall(r"\$\{?pkgdir\}?/usr/bin/([\w.+-]+)", text)
    return dict(name=shell_var(text, "pkgname"), version=shell_var(text, "pkgver"), description=shell_var(text, "pkgdesc"),
                license=shell_var(text, "license"), homepage=shell_var(text, "url"), bins=list(dict.fromkeys(bins)))


def read_srcinfo(s, rel, text):
    get = lambda key: (re.search(r"^[ \t]*" + key + r"\s*=\s*(.+)$", text, re.M) or [None, None])[1]  # noqa: E731
    return dict(name=get("pkgname"), version=get("pkgver"), description=get("pkgdesc"), license=get("license"), homepage=get("url"))


def read_regex_fields(patterns):
    """A reader that takes each field from the first match of its pattern."""
    def reader(s, rel, text):
        out = {}
        for key, pattern in patterns.items():
            if key == "bins":
                out[key] = [b for b in re.findall(pattern, text, re.M) if "$" not in b]
            else:
                m = re.search(pattern, text, re.M)
                out[key] = m.group(1).strip() if m else None
        return out
    return reader


def read_pro(s, rel, text):
    target = re.search(r"^[ \t]*TARGET\s*=\s*([\w.-]+)\s*$", text, re.M)
    template = re.search(r"^[ \t]*TEMPLATE\s*=\s*(\w+)", text, re.M)
    version = re.search(r"^[ \t]*VERSION\s*=\s*([\d.]+)\s*$", text, re.M)
    is_app = not template or template.group(1) == "app"
    return dict(name=target.group(1) if target else None, version=version.group(1) if version else None,
                bins=[target.group(1)] if target and is_app else [])


def read_makefile(s, rel, text):
    targets = re.findall(r"^([A-Za-z][\w.-]*)\s*:(?!=)", text, re.M)
    return dict(scripts={t: "" for t in targets if t.upper() != t or len(t) < 3})


def read_yaml_fields(s, rel, text):
    data, _ = formats.read_yaml(text)
    if not isinstance(data, dict) and (data is not None or any(
            line.strip() and not line.lstrip().startswith("#") for line in text.split("\n"))):
        s.malformed(rel, "is not a YAML mapping")
    s.parsed[rel] = data if isinstance(data, dict) else {}
    data = s.parsed[rel]
    execs = data.get("executables")
    return dict(name=_str(data.get("name")), version=_str(data.get("version")), description=_str(data.get("description")),
                homepage=_str(data.get("homepage")), repository=_str(data.get("repository")),
                bins=list(execs) if isinstance(execs, dict) else [])


def read_skill(s, rel, text):
    data, _, certain = formats.frontmatter(text)
    if not certain:
        s.malformed(rel, "has frontmatter that could not be read")
    s.parsed[rel] = data = data or {}
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    return dict(name=_str(data.get("name")), description=_str(data.get("description")), license=_str(data.get("license")),
                version=_str(str(meta.get("version") or data.get("version") or "")))


def read_json_fields(s, rel, text):
    data = formats.parse_json(text)
    if not isinstance(data, dict):
        if not rel.endswith(".jsonc"):  # JSON with comments, which no reader here parses
            s.malformed(rel, "is not a JSON object")
        return {}
    name = posixpath.basename(rel)
    if name == "manifest.json" and "manifest_version" not in data and "minAppVersion" not in data:
        return None
    s.parsed[rel] = data
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    bins = data.get("bin") if isinstance(data.get("bin"), list) else []
    scripts = data.get("scripts") if name == "composer.json" and isinstance(data.get("scripts"), dict) else {}
    return dict(name=_str(data.get("name")), version=_str(data.get("version") or meta.get("version")),
                description=_str(data.get("description") or meta.get("description")), license=_str(data.get("license")),
                homepage=_str(data.get("homepage")), repository=_url(data.get("repository")),
                bins=[posixpath.basename(b) for b in bins if isinstance(b, str)],
                scripts={k: v for k, v in scripts.items() if isinstance(v, str)})


MANIFEST_READERS = {
    "pyproject": read_pyproject, "setup.cfg": read_setup_cfg, "setup.py": read_setup_py,
    "package.json": read_package_json, "Cargo.toml": read_cargo, "PKGBUILD": read_pkgbuild, ".SRCINFO": read_srcinfo,
    "*.pro": read_pro, "Makefile": read_makefile, "action.yml": read_yaml_fields, "compose": read_yaml_fields,
    "pubspec.yaml": read_yaml_fields, "SKILL.md": read_skill, "plugin.json": read_json_fields,
    "marketplace.json": read_json_fields, "gemini-extension.json": read_json_fields, "manifest.json": read_json_fields,
    "composer.json": read_json_fields, "deno.json": read_json_fields,
    "go.mod": read_regex_fields({"name": r"^module\s+(\S+)"}),
    "*.gemspec": read_regex_fields({"name": r"\.name\s*=\s*['\"]([^'\"]+)", "version": r"\.version\s*=\s*['\"]([^'\"]+)",
                                    "description": r"\.summary\s*=\s*['\"]([^'\"]+)", "license": r"\.licenses?\s*=\s*\[?\s*['\"]([^'\"]+)",
                                    "homepage": r"\.homepage\s*=\s*['\"]([^'\"]+)", "bins": r"\.executables\s*=\s*\[?\s*['\"]([\w.-]+)"}),
    "pom.xml": read_regex_fields({"name": r"^\s{0,4}<artifactId>([^<]+)", "version": r"^\s{0,4}<version>([^<]+)",
                                  "description": r"^\s{0,4}<description>([^<]+)", "homepage": r"^\s{0,4}<url>([^<]+)"}),
    "build.gradle": read_regex_fields({"version": r"^version\s*=?\s*['\"]([^'\"]+)", "description": r"^description\s*=?\s*['\"]([^'\"]+)"}),
    "CMakeLists.txt": read_regex_fields({"name": r"^[ \t]*project\(\s*([\w.-]+)", "version": r"^[ \t]*project\([^)]*VERSION\s+([\d.]+)",
                                         "description": r"^[ \t]*project\([^)]*DESCRIPTION\s+\"([^\"]+)\"",
                                         "bins": r"^[ \t]*(?:qt6?_add_executable|add_executable)\(\s*([\w.-]+)"}),
    "meson.build": read_regex_fields({"name": r"^[ \t]*project\(\s*'([^']+)'", "version": r"^[ \t]*version\s*:\s*'([^']+)'",
                                      "license": r"license\s*:\s*'([^']+)'", "bins": r"^[ \t]*(?:\w+\s*=\s*)?executable\(\s*'([^']+)'"}),
    "flake.nix": read_regex_fields({"description": r"^[ \t]*description\s*=\s*\"([^\"]+)\""}),
    "Package.swift": read_regex_fields({"name": r"Package\(\s*name:\s*\"([^\"]+)\"",
                                        "bins": r"\.executable(?:Target)?\(\s*name:\s*\"([^\"]+)\""}),
    "*.csproj": read_regex_fields({"name": r"<(?:PackageId|AssemblyName)>([^<]+)<", "version": r"<Version>([^<]+)<",
                                   "description": r"<Description>([^<]+)<", "license": r"<PackageLicenseExpression>([^<]+)<",
                                   "bins": r"<ToolCommandName>([^<]+)<"}),
    "mix.exs": read_regex_fields({"name": r"\bapp:\s*:(\w+)", "version": r"\bversion:\s*\"([^\"]+)\"",
                                  "description": r"\bdescription:\s*\"([^\"]+)\""}),
}


def scan_manifests(s):
    """Index the manifests of the shipped project (not tests, examples or tooling)."""
    for rel in s.files:
        name = rel.rsplit("/", 1)[-1]
        mtype = MANIFEST_NAMES.get(name) or MANIFEST_SUFFIXES.get(posixpath.splitext(name)[1])
        if name.startswith("Dockerfile.") or name.endswith(".Dockerfile"):
            mtype = "Dockerfile"
        if not mtype or not s.product(rel):
            continue
        if mtype == "SKILL.md" and rel != "SKILL.md" and rel.split("/")[-3:-2] != ["skills"]:
            continue
        text = s.read(rel)
        if text is None:
            continue
        reader = MANIFEST_READERS.get(mtype)
        try:
            fields = reader(s, rel, text) if reader else {}
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as err:  # a shape no reader expects
            s.malformed(rel, f"could not be read ({type(err).__name__})")
            fields = {}
        if fields is not None:
            s.manifest(rel, mtype, **fields)


def manifests_of(s, *types):
    return [m for m in s.manifests if m["type"] in types]


# ---------------------------------------------------------------- source code


def leading_lits(args):
    """Literal arguments at the start of a call's '(...)' text."""
    out, rest = [], args[1:] if args[:1] in "({" else args
    while True:
        rest = rest.lstrip(" \t\n")
        m = STR_RE.match(rest)
        if not m:
            return out
        out.append(next(g for g in m.groups() if g is not None))
        rest = rest[m.end():].lstrip(" \t\n")
        if not rest.startswith(","):
            return out
        rest = rest[1:]


def calls(src, pattern, flags=0, area="sources"):
    """(match, argument text, line) for each call matched by pattern, up to CALL_LIMIT.

    The argument text runs from the bracket the match ends at to its partner; it is
    empty when the match ends elsewhere (a decorator used bare, as `@mcp.tool`).
    Past the limit, the file is noted as a gap in the surface area named."""
    for count, m in enumerate(re.finditer(pattern, src.code, flags)):
        if count >= CALL_LIMIT:
            if src.scanner is not None:
                src.scanner.capped(src.path, src.line(m.start()), area)
            return
        opens = m.end() > m.start() and src.code[m.end() - 1] in _PAIRS
        yield m, balanced(src.code, m.end() - 1) if opens else "", src.line(m.start())


def def_after(code, pos):
    m = re.compile(r"\b(?:async\s+)?def\s+(\w+)\s*\(").search(code, pos)
    return m


def docstring(code, pos):
    m = re.compile(r"\)[^:\n]*:\s*\n\s*(?:\"\"\"|''')\s*([^\n\"']+)").search(code, pos, pos + 2000)
    return m.group(1).strip() if m else None


def py_source(s, src):
    code, path = src.code, src.path
    if "add_argument" in code or "add_parser" in code or "ArgumentParser" in code:
        for m, args, line in calls(src, r"\bArgumentParser\(", area="cli"):
            prog = kwarg(args, "prog")
            if prog:
                s.surface("cli", {"name": prog, "path": path, "line": line, "kind": "command", "help": kwarg(args, "description")})
        for m, args, line in calls(src, r"\.add_parser\(", area="cli"):
            name = lit_at(args[1:])
            if name is None:
                s.dynamic(path, line, "add_parser")
            elif not re.search(r"help\s*=\s*(argparse\.)?SUPPRESS", args):
                s.surface("cli", {"name": name, "path": path, "line": line, "kind": "subcommand", "help": kwarg(args, "help")})
        for m, args, line in calls(src, r"\.add_argument\(", area="cli"):
            names = leading_lits(args)
            if not names:
                s.dynamic(path, line, "add_argument")
            elif best_flag(names) and not re.search(r"help\s*=\s*(argparse\.)?SUPPRESS", args):
                s.surface("cli", {"name": best_flag(names), "path": path, "line": line, "kind": "option", "help": kwarg(args, "help")})
    if re.search(r"^[ \t]*(?:import|from)\s+(?:click|typer)\b", code, re.M):
        for m, args, line in calls(src, r"^[ \t]*@([\w.]+)\.(?:command|group)\(", re.M, area="cli"):
            if re.search(r"hidden\s*=\s*True", args):
                continue
            name = lit_at(args[1:]) or kwarg(args, "name")
            fn = def_after(code, m.end())
            kind = "command" if m.group(1) in ("click", "typer") else "subcommand"
            if name is None and fn and not fn.group(1).startswith("_") and kind == "subcommand":
                # A root group runs under the installed script's name, not its function's.
                name = fn.group(1).replace("_", "-")
            help_text = kwarg(args, "help") or (docstring(src.text, fn.end()) if fn else None)
            s.surface("cli", {"name": name, "path": path, "line": line, "kind": kind, "help": help_text})
        for m, args, line in calls(src, r"(?:^[ \t]*@[\w.]+\.option|\btyper\.Option)\(", re.M, area="cli"):
            names = [n for n in lits(args) if re.match(r"-{1,2}\w[\w-]*$", n)] if "typer" in m.group(0) else leading_lits(args)
            if best_flag(names) and not re.search(r"hidden\s*=\s*True", args):
                s.surface("cli", {"name": best_flag(names), "path": path, "line": line, "kind": "option", "help": kwarg(args, "help")})
    if re.search(r"\b(flask|fastapi|starlette|quart|sanic|bottle|litestar)\b", code, re.I):
        for m, args, line in calls(src, r"^[ \t]*@[\w.]+\.(route|get|post|put|patch|delete|websocket)\(", re.M, area="routes"):
            route = lit_at(args[1:])
            if route is None:
                s.dynamic(path, line, "route")
            elif route.startswith("/"):
                listed = re.search(r"\bmethods\s*=\s*[\[(]([^\])]*)", args) if m.group(1) == "route" else None
                methods = [x.upper() for x in lits(listed.group(1))] if listed else []
                for method in methods or ["GET" if m.group(1) == "route" else m.group(1).upper()]:
                    s.surface("routes", {"method": method, "route": route, "path": path, "line": line})
    if PY_MCP_IMPORT.search(code):
        s.flags["mcp"] += 1
        s.flags.setdefault("mcp_at", (path, find_line(code, PY_MCP_IMPORT.pattern)))
        s.mcp_instances.update(m.group(1) for m in PY_MCP_SERVER.finditer(code))
        py_tools(s, src)
    elif PY_TOOL_OWNER.search(code):
        s.mcp_pending.append((src, py_tools, PY_TOOL_OWNER))  # perhaps a server made in another module


PY_MCP_IMPORT = re.compile(r"^[ \t]*(?:from|import)\s+(?:mcp|fastmcp)\b", re.M)
PY_MCP_SERVER = re.compile(r"^[ \t]*(\w+)\s*(?::[^=\n]*)?=\s*(?:[\w.]+\.)?(?:FastMCP|MCPServer|Server)\(", re.M)
PY_TOOL_OWNER = re.compile(r"^[ \t]*@([\w.]+)\.tool\b|(?<![@\w.])([\w.]+)\.add_tool\(", re.M)


def py_tools(s, src):
    """MCP tools a Python module registers, by decorator or by add_tool."""
    code, path = src.code, src.path
    for m, args, line in calls(src, r"^[ \t]*@[\w.]+\.tool\b\(?", re.M, area="tools"):
        args = args or "()"
        name = kwarg(args, "name") or lit_at(args[1:])
        if name is None and re.search(r"\bname\s*=", args):
            s.dynamic(path, line, "tool registration")  # named by a variable: the function's name is not it
            continue
        fn = def_after(code, m.end())
        if name is None and fn:
            name = fn.group(1)
        desc = kwarg(args, "description") or (docstring(src.text, fn.end()) if fn else None)
        s.surface("tools", {"name": name, "path": path, "line": line, "description": desc})
    for m, args, line in calls(src, r"(?<![@\w.])[\w.]+\.(?:add_tool|tool)\(|(?<![\w.])(?:types\.)?Tool\(",
                               area="tools"):
        name = kwarg(args, "name")
        if name:
            s.surface("tools", {"name": name, "path": path, "line": line, "description": kwarg(args, "description")})
        elif "Tool(" not in m.group(0) or "name=" in args:
            s.dynamic(path, line, "tool registration")


JS_CLI = re.compile(r"""(?:require\(\s*|from\s+)['"](?:commander|yargs|cac|sade|@commander-js/[\w-]+)""")
JS_SERVER = re.compile(r"""(?:require\(\s*|from\s+)['"](?:express|fastify|koa|@koa/router|hono|restify|@hapi/hapi)['"]""")


def js_source(s, src):
    code, path = src.code, src.path
    if JS_CLI.search(code):
        for m, args, line in calls(src, r"\.(command|option|requiredOption|name)\(", area="cli"):
            first = lit_at(args[1:])
            if first is None:
                continue
            rest = leading_lits(args)
            help_text = rest[1] if len(rest) > 1 else kwarg(args, "describe") or kwarg(args, "description")
            if m.group(1) == "name":
                s.surface("cli", {"name": first, "path": path, "line": line, "kind": "command", "help": None})
            elif m.group(1) == "command" and not re.search(r"hidden\s*:\s*true", args):
                s.surface("cli", {"name": first.split()[0], "path": path, "line": line, "kind": "subcommand", "help": help_text})
            elif m.group(1) != "command":
                flag = best_flag(re.findall(r"-{1,2}[\w-]+", first)) or "--" + first
                s.surface("cli", {"name": flag, "path": path, "line": line, "kind": "option", "help": help_text})
    if JS_SERVER.search(code):
        for m, args, line in calls(src, r"\b\w+\.(get|post|put|patch|delete|all)\(", area="routes"):
            route = lit_at(args[1:])
            if route and route.startswith("/"):
                s.surface("routes", {"method": m.group(1).upper(), "route": route, "path": path, "line": line})
    if "@modelcontextprotocol/sdk" in code or re.search(r"""from\s+['"]fastmcp['"]""", code):
        s.flags["mcp"] += 1
        s.flags.setdefault("mcp_at", (path, find_line(code, r"modelcontextprotocol|fastmcp")))
        s.mcp_instances.update(m.group(1) for m in JS_MCP_SERVER.finditer(code))
        js_tools(s, src)
    elif JS_TOOL_OWNER.search(code):
        s.mcp_pending.append((src, js_tools, JS_TOOL_OWNER))  # perhaps a server made in another module
    for m in re.finditer(r"""accelerator\s*:\s*['"]([^'"]+)['"]""", code):
        label = re.search(r"""label\s*:\s*['"]([^'"]+)['"]""", code[max(0, m.start() - 200):m.end() + 200])
        s.surface("shortcuts", {"keys": m.group(1), "path": path, "line": src.line(m.start()), "text": label.group(1) if label else None})


JS_MCP_SERVER = re.compile(r"\b(?:const|let|var)\s+(\w+)\s*(?::[^=\n]*)?=\s*new\s+(?:[\w$.]+\.)?(?:McpServer|Server|FastMCP)\(")
JS_TOOL_OWNER = re.compile(r"(?<![\w$.])([\w$.]+)\.(?:tool|registerTool|addTool)\(")


def js_tools(s, src):
    """MCP tools a JavaScript or TypeScript module registers."""
    path = src.path
    for m, args, line in calls(src, r"(?<![\w$.])[\w$.]+\.(tool|registerTool|addTool)\(", area="tools"):
        name = kwarg(args, "name") if m.group(1) == "addTool" else lit_at(args[1:])
        if name is None:
            s.dynamic(path, line, m.group(1))
            continue
        rest = leading_lits(args)
        desc = kwarg(args, "description") or (rest[1] if len(rest) > 1 and m.group(1) == "tool" else None)
        s.surface("tools", {"name": name, "path": path, "line": line, "description": desc})


def pending_tools(s):
    """Tool registrations in modules that do not import an MCP SDK themselves.

    Where they go through a server object another module made, they are read
    as that server's tools; in an MCP project, any other is left as a gap.
    """
    for src, reader, owner_re in s.mcp_pending:
        if not s.flags["mcp"]:
            return
        owners = [(m, next((g for g in m.groups() if g), "").split(".")[0]) for m in owner_re.finditer(src.code)]
        if any(owner in s.mcp_instances for _, owner in owners):
            reader(s, src)
        else:
            for m, _ in owners[:CALL_LIMIT]:
                s.dynamic(src.path, src.line(m.start()), "tool registration")


def rust_items(body):
    """Split a {...} body at top-level commas into (offset, text) items."""
    items, depth, start = [], 0, 1
    for i in range(1, len(body) - 1):
        ch = body[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append((start, body[start:i]))
            start = i + 1
    items.append((start, body[start:len(body) - 1]))
    return items


def doc_comment(src, line):
    out = []
    while line > 1 and src.raw_line(line - 1).strip().startswith(("///", "#[")):
        line -= 1
        text = src.raw_line(line).strip()
        if text.startswith("///"):
            out.insert(0, text[3:].strip())
    return " ".join(out) or None


RUST_ATTRS = re.compile(r"\s*(?:#\[(?:[^\[\]]|\[[^\]]*\])*\]\s*)*")


def clap_flag(attrs, plain, field):
    """The flag a clap field declares: --long, -s, or None for a positional."""
    m = re.search(r"\blong\s*=\s*\"([^\"]+)\"", attrs)
    if m:
        return "--" + m.group(1)
    if re.search(r"\blong\b", plain):
        return "--" + field.replace("_", "-")
    m = re.search(r"\bshort\s*=\s*'(.)'", attrs)
    if m:
        return "-" + m.group(1)
    return "-" + field[0] if re.search(r"\bshort\b", plain) else None


def rust_source(s, src):
    code, path = src.code, src.path
    if "clap" in code or "derive(Parser" in code:
        for count, m in enumerate(re.finditer(r"#\[derive\(([^)]*)\)\]", code)):
            derives = m.group(1)
            if count >= CALL_LIMIT:
                s.capped(path, src.line(m.start()), "cli")
                break
            if not re.search(r"\b(Parser|Subcommand|Args)\b", derives):
                continue
            decl = re.compile(r"\s*(?:#\[(?:[^\[\]]|\[[^\]]*\])*\]\s*)*(?:pub(?:\([^)]*\))?\s+)?(enum|struct)\s+\w+[^{;]*\{").match(code, m.end())
            if not decl:
                continue
            header = code[max(code.rfind("}", 0, m.start()), code.rfind(";", 0, m.start())) + 1:decl.end()]
            cmd = re.search(r"#\[(?:command|clap)\([^\]]*\bname\s*=\s*\"([^\"]+)\"", header)
            if cmd and "Parser" in derives:
                s.surface("cli", {"name": cmd.group(1), "path": path, "line": src.line(m.start()), "kind": "command", "help": None})
            brace = decl.end() - 1
            items = rust_items(balanced(code, brace, 20000))
            if len(items) > CALL_LIMIT:
                s.capped(path, src.line(brace), "cli")
            for offset, item in items[:CALL_LIMIT]:
                prefix = RUST_ATTRS.match(item)
                attrs, bare = prefix.group(0), item[prefix.end():].strip()
                plain = STR_RE.sub('""', attrs)
                if not bare or re.search(r"\bhide\s*=\s*true", plain):
                    continue
                line = src.line(brace + offset + prefix.end())
                help_text = (re.search(r"\b(?:help|about)\s*=\s*\"([^\"]*)\"", attrs) or [None, None])[1] or doc_comment(src, line)
                if decl.group(1) == "enum":
                    variant = re.match(r"([A-Z]\w*)", bare)
                    named = re.search(r"\bname\s*=\s*\"([^\"]+)\"", attrs)
                    if variant:
                        s.surface("cli", {"name": named.group(1) if named else kebab(variant.group(1)), "path": path,
                                          "line": line, "kind": "subcommand", "help": help_text})
                    continue
                field = re.match(r"(?:pub(?:\([^)]*\))?\s+)?(\w+)\s*:", bare)
                if field and re.search(r"\b(arg|clap|structopt)\(", plain) and not re.search(r"\b(subcommand|flatten)\b", plain):
                    flag = clap_flag(attrs, plain, field.group(1))
                    if flag:
                        s.surface("cli", {"name": flag, "path": path, "line": line, "kind": "option", "help": help_text})
        for m in re.finditer(r"\.subcommand\(\s*(?:Command|App|SubCommand)::(?:new|with_name)\(\s*\"([^\"]+)\"", code):
            s.surface("cli", {"name": m.group(1), "path": path, "line": src.line(m.start()), "kind": "subcommand", "help": None})
        for m in re.finditer(r"Arg::(?:new|with_name)\(\s*\"[^\"]+\"\s*\)[^;]{0,300}?\.long\(\s*\"([^\"]+)\"", code, re.S):
            s.surface("cli", {"name": "--" + m.group(1), "path": path, "line": src.line(m.start()), "kind": "option", "help": None})
    if re.search(r"\b(axum|actix_web|rocket|warp|poem)\b", code):
        for m in re.finditer(r"\.route\(\s*\"(/[^\"]*)\"\s*,", code):
            args = balanced(code, code.index("(", m.start()))
            for method in re.findall(r"\b(get|post|put|patch|delete)\s*\(", args) or ["any"]:
                s.surface("routes", {"method": method.upper(), "route": m.group(1), "path": path, "line": src.line(m.start())})
        for m in re.finditer(r"#\[(get|post|put|patch|delete)\(\s*\"(/[^\"]*)\"", code):
            s.surface("routes", {"method": m.group(1).upper(), "route": m.group(2), "path": path, "line": src.line(m.start())})
    if "rmcp" in code:
        s.flags["mcp"] += 1
        s.flags.setdefault("mcp_at", (path, find_line(code, r"rmcp")))
        for m in re.finditer(r"#\[tool\(([^\]]*)\)\]\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", code):
            name = kwarg(m.group(1), "name") or m.group(2)
            s.surface("tools", {"name": name, "path": path, "line": src.line(m.start()), "description": kwarg(m.group(1), "description")})


def go_source(s, src):
    code, path = src.code, src.path
    for m, body, line in calls(src, r"(\w+)\s*:?=\s*&cobra\.Command\s*\{|&cobra\.Command\s*\{", area="cli"):
        use = re.search(r"\bUse:\s*\"([^\"]+)\"", body)
        if use and not re.search(r"\bHidden:\s*true", body):
            kind = "command" if "root" in (m.group(1) or "").lower() else "subcommand"
            s.surface("cli", {"name": use.group(1).split()[0], "path": path, "line": line, "kind": kind,
                              "help": (re.search(r"\bShort:\s*\"([^\"]*)\"", body) or [None, None])[1]})
    for m, args, line in calls(src, r"(?:\.(?:Persistent)?Flags\(\)|\bflag)\.(?:String|Bool|Int|Int64|Uint|Uint64|Float64|Duration|StringSlice|Count)(?:Var)?P?\(", area="cli"):
        names = lits(args)
        if names:
            prefix = "-" if m.group(0).startswith("flag") else "--"
            s.surface("cli", {"name": prefix + names[0], "path": path, "line": line, "kind": "option", "help": names[-1] if len(names) > 1 else None})
    if re.search(r"\"net/http\"|gin-gonic|go-chi|labstack/echo|gorilla/mux", code):
        for m in re.finditer(r"\.(?:HandleFunc|Handle)\(\s*\"([^\"]+)\"", code):
            parts = m.group(1).split(None, 1)
            method, route = (parts[0], parts[1]) if len(parts) == 2 else ("ANY", parts[0])
            if route.startswith("/"):
                s.surface("routes", {"method": method, "route": route, "path": path, "line": src.line(m.start())})
        for m in re.finditer(r"\.(GET|POST|PUT|PATCH|DELETE|Get|Post|Put|Patch|Delete)\(\s*\"(/[^\"]*)\"", code):
            s.surface("routes", {"method": m.group(1).upper(), "route": m.group(2), "path": path, "line": src.line(m.start())})
    if "mcp-go" in code or "modelcontextprotocol/go-sdk" in code:
        s.flags["mcp"] += 1
        s.flags.setdefault("mcp_at", (path, find_line(code, r"mcp-go|go-sdk")))
        for m, args, line in calls(src, r"\bmcp\.NewTool\(", area="tools"):
            name = lit_at(args[1:])
            if name is None:
                s.dynamic(path, line, "NewTool")
            else:
                desc = re.search(r"WithDescription\(\s*\"([^\"]*)\"", args)
                s.surface("tools", {"name": name, "path": path, "line": line, "description": desc.group(1) if desc else None})


def qt_option_names(inner):
    """Names of a QCommandLineOption's first argument, and the text after it."""
    m = re.match(r'QStringList\s*(?:\(\s*\))?((?:\s*<<\s*"[^"]*")+)', inner)
    if m:
        return lits(m.group(1)), inner[m.end():]
    inner = re.sub(r"^QStringList\s*", "", inner)
    if inner.startswith("{"):
        group = balanced(inner, 0)
        return lits(group), inner[len(group):]
    m = STR_RE.match(inner)
    return ([next(g for g in m.groups() if g is not None)], inner[m.end():]) if m else ([], inner)


def cpp_source(s, src):
    code, path = src.code, src.path
    if "QCommandLine" in code:
        for m, args, line in calls(src, r"\baddOption\(|\bQCommandLineOption\s+\w+\s*[({]", area="cli"):
            inner = args[1:].lstrip()
            if m.group(0).startswith("addOption") and inner.startswith("{"):
                inner = inner[1:].lstrip()  # addOption({...}) builds the option in place
            names, rest = qt_option_names(inner)
            if not names:
                continue
            texts = [t for t in lits(rest) if t not in names]
            flag = max(names, key=len)
            s.surface("cli", {"name": ("--" if len(flag) > 1 else "-") + flag, "path": path, "line": line, "kind": "option",
                              "help": next((t for t in texts if " " in t), texts[0] if texts else None)})
    for m in re.finditer(r"QKeySequence\(\s*(?:tr\(\s*|QStringLiteral\(\s*)?\"([^\"]+)\"", code):
        s.surface("shortcuts", {"keys": m.group(1), "path": path, "line": src.line(m.start()), "text": None})
    for m in re.finditer(r"set_accels_for_action\(\s*\"([^\"]+)\"\s*,\s*[\[{(]([^\]})]*)", code):
        for keys in lits(m.group(2)):
            s.surface("shortcuts", {"keys": keys, "path": path, "line": src.line(m.start()), "text": m.group(1)})


def qml_source(s, src):
    code, path = src.code, src.path
    for m, body, line in calls(src, r"(?<![\w.])(Shortcut|Action)\s*\{", area="shortcuts"):
        inner = body[1:-1]
        prop = r"\bsequences?\s*:\s*(\[[^\]]*\]|\"[^\"]*\"|StandardKey\.\w+)" if m.group(1) == "Shortcut" \
            else r"\bshortcut\s*:\s*(\"[^\"]*\"|StandardKey\.\w+)"
        found = re.search(prop, re.sub(r"\b(?:Shortcut|Action)\s*\{.*", "", inner, flags=re.S) or inner)
        if not found and re.search(r"\bsequences?\s*:", inner):
            s.dynamic(path, line, "Shortcut")  # keys come from a model or binding, not a literal
        if not found or re.search(r"\benabled\s*:\s*false\b", inner):
            continue
        keys = lits(found.group(1)) + re.findall(r"StandardKey\.\w+", found.group(1))
        label = re.search(r"\btext\s*:\s*(?:qsTr\(\s*)?\"([^\"]+)\"", inner)
        action = re.search(r"\bon(?:Activated|Triggered)\s*:\s*([^\s;{}][^;\n]*)", inner)
        text = label.group(1) if label else action.group(1).strip().rstrip("}").strip() if action else None
        for key in keys:
            s.surface("shortcuts", {"keys": key, "path": path, "line": line, "text": text})


def shell_source(s, src):
    """Subcommands and options of a script that dispatches on its first argument."""
    code, path = src.code, src.path
    for m in re.finditer(r"\bcase\s+\"?\$\{?1(?::-[^}]*)?\}?\"?\s+in\b", code):
        depth, end = 1, m.end() + 4000
        for token in re.finditer(r"\b(case|esac)\b", code[m.end():m.end() + 20000]):
            depth += 1 if token.group(1) == "case" else -1
            if depth == 0:
                end = m.end() + token.start()
                break
        body_start, body = m.end(), code[m.end():end]
        indent = None
        for arm in re.finditer(r"^([ \t]*)\(?([^\s()#][^()\n]*)\)", body, re.M):
            indent = arm.group(1) if indent is None else indent
            names = [w.strip().strip("\"'") for w in arm.group(2).split("|")]
            if arm.group(1) != indent or not all(re.match(r"-{0,2}\w[\w.-]*$", n) for n in names):
                continue
            flag = best_flag(names)
            name = flag if flag and (flag.startswith("--") or all(n.startswith("-") for n in names)) else next(n for n in names if not n.startswith("-"))
            s.surface("cli", {"name": name, "path": path, "line": src.line(body_start + arm.start(2)),
                              "kind": "option" if name.startswith("-") else "subcommand", "help": None})


ENV_PATTERNS = {
    "Python": r"os\.environ\[\s*[\"']([A-Z_][A-Z0-9_]*)|(?:environ\.get|os\.getenv)\(\s*[\"']([A-Z_][A-Z0-9_]*)",
    "JavaScript": r"process\.env\.([A-Z_][A-Z0-9_]*)|process\.env\[\s*[\"']([A-Z_][A-Z0-9_]*)|import\.meta\.env\.([A-Z_][A-Z0-9_]*)|Deno\.env\.get\(\s*[\"']([A-Z_][A-Z0-9_]*)",
    "Rust": r"env::var(?:_os)?\(\s*\"([A-Z_][A-Z0-9_]*)\"",
    "Go": r"os\.(?:Getenv|LookupEnv)\(\s*\"([A-Z_][A-Z0-9_]*)\"",
    "C": r"\b(?:qgetenv|getenv|secure_getenv|qEnvironmentVariable(?:IsSet|IsEmpty|IntValue)?)\(\s*\"([A-Z_][A-Z0-9_]*)\"",
    "Ruby": r"ENV(?:\[|\.fetch\()\s*[\"']([A-Z_][A-Z0-9_]*)",
}
FAMILY = {"Python": "py", "JavaScript": "js", "TypeScript": "js", "Rust": "rs", "Go": "go", "C": "cpp", "C++": "cpp", "QML": "js", "Ruby": "rb"}
SIGNALS = {
    "network": {
        "py": r"\b(requests\.(?:get|post|put|patch|delete|head|request|Session)|httpx\.(?:get|post|put|delete|request|Client|AsyncClient)|urllib\.request\.urlopen|aiohttp\.ClientSession|websockets\.connect|socket\.create_connection|boto3\.(?:client|resource))\b",
        "js": r"(@aws-sdk/client-[\w-]+)|(?<![\w.])(fetch)\(|\b(axios(?:\.(?:get|post|put|delete|request|create))?)\b|\b(new WebSocket)\(|\b(XMLHttpRequest)\b|\b(https?\.(?:request|get))\(",
        "rs": r"\b(reqwest::\w+|ureq::\w+|hyper::Client|TcpStream::connect)",
        "go": r"\b(http\.(?:Get|Post|NewRequest(?:WithContext)?)|net\.Dial(?:Timeout)?)\b",
        "cpp": r"\b(QNetworkAccessManager|QWebSocket|QTcpSocket|QUdpSocket|curl_easy_init)\b",
    },
    "storage": {
        "py": r"\b(sqlite3\.connect|shelve\.open|dbm\.open|platformdirs\.\w+|appdirs\.\w+|redis\.Redis|psycopg2?\.connect|pymongo\.MongoClient|create_engine)\b",
        "js": r"\b(localStorage|sessionStorage|indexedDB|fs\.(?:writeFile(?:Sync)?|appendFile(?:Sync)?)|mongoose\.connect)\b|(better-sqlite3)",
        "rs": r"\b(rusqlite::\w+|sled::open|dirs::(?:data|config|cache)_dir|directories::ProjectDirs|fs::write)\b",
        "go": r"\b(sql\.Open|os\.WriteFile|os\.UserConfigDir|os\.UserCacheDir|bolt\.Open|badger\.Open)\b",
        "cpp": r"\b(QSettings|QStandardPaths::writableLocation|QSaveFile|QSqlDatabase|sqlite3_open)\b",
    },
    "telemetry": {"*": r"\b(posthog(?=[.(\"'-])|sentry_sdk\.init|Sentry\.init|@sentry/[\w-]+|mixpanel(?=[.(\"'])|amplitude\.(?:init|track|getInstance)|opentelemetry|ddtrace|gtag\(|googletagmanager|plausible\.io|segment\.(?:track|identify)|analytics\.(?:track|identify))"},
    "account": {"*": r"\b(oauth2?\b|OAuth2?\w*|passport\.authenticate|next-auth|NextAuth|signIn\(|login\(|keyring\.(?:get|set)_password|getpass\.getpass|auth0|firebase/auth|CognitoIdentity\w*)"},
}
SIGNAL_RES = {cat: {fam: re.compile(p) for fam, p in table.items()} for cat, table in SIGNALS.items()}
ENV_RES = {lang: re.compile(p) for lang, p in ENV_PATTERNS.items()}
HANDLERS = {"Python": py_source, "JavaScript": js_source, "TypeScript": js_source, "Rust": rust_source, "Go": go_source,
            "C": cpp_source, "C++": cpp_source, "QML": qml_source, "Shell": shell_source}


def scan_sources(s):
    for rel in s.code_files(*HANDLERS):
        src = s.source(rel)
        if src is None:
            continue
        HANDLERS[src.lang](s, src)
        env_re = ENV_RES.get("JavaScript" if src.lang == "TypeScript" else "C" if src.lang == "C++" else src.lang)
        if env_re:
            for m in env_re.finditer(src.code):
                name = next(g for g in m.groups() if g)
                if name not in SYSTEM_ENV and not name.startswith("CARGO_"):
                    s.surface("env", {"name": name, "path": rel, "line": src.line(m.start())})
        family = FAMILY.get(src.lang)
        for category, table in SIGNAL_RES.items():
            pattern = table.get(family) or table.get("*")
            if pattern is None:
                continue
            for m in pattern.finditer(src.code):
                s.signal(category, rel, src.line(m.start()), next(g for g in m.groups() if g))
    pending_tools(s)


# ---------------------------------------------------------------- ecosystems


def python_ecosystem(s):
    has_bins = False
    for m in manifests_of(s, "pyproject", "setup.cfg", "setup.py"):
        path, text = m["path"], s.read(m["path"])
        for name in m["bins"]:
            has_bins = True
            line = find_line(text, r"^[ \t]*[\"']?" + re.escape(name) + r"[\"']?\s*=", r"scripts\]|console_scripts")
            s.entry(name, path, line, "console_scripts")
        if m["name"]:
            s.channel("pypi", m["name"], path, find_line(text, r"^[ \t]*name\s*="))
        for os_name, platform in (("POSIX :: Linux", "linux"), ("MacOS", "macos"), ("Microsoft :: Windows", "windows"), ("OS Independent", "any")):
            if "Operating System :: " + os_name in text:
                s.platform(platform, path, find_line(text, re.escape(os_name)))
    python_manifests = manifests_of(s, "pyproject", "setup.cfg", "setup.py")
    if not any(m["name"] or m["bins"] for m in python_manifests):
        # No package (at most tool settings such as [tool.ruff]): a root script with a command line is the program.
        for rel in s.code_files("Python"):
            src = s.source(rel) if "/" not in rel else None
            main = src and re.search(r"^if\s+__name__\s*==\s*['\"]__main__['\"]", src.code, re.M)
            if main and re.search(r"^[ \t]*(?:import|from)\s+(?:argparse|click|typer)\b", src.code, re.M):
                s.entry(rel[:-3] if rel.endswith(".py") else rel, rel, src.line(main.start()), "script")
    if not python_manifests:
        return
    packages = sorted({f.rsplit("/", 1)[0] for f in s.files if f.endswith("/__init__.py") and s.product(f)
                       and f.count("/") <= (2 if f.startswith("src/") else 1)})
    service = bool(s.surfaces["routes"]) or s.flags["mcp"]
    for pkg in packages:
        init = pkg + "/__init__.py"
        src = s.source(init)
        if src is None:
            continue
        exported = re.search(r"^__all__\s*(?::[^=]*)?=\s*[\[(]([^\])]*)[\])]", src.code, re.M)
        if exported:
            s.kind("library", None, "high", init, src.line(exported.start()), "__all__ lists the public names")
        elif not has_bins and not service:
            s.kind("library", None, "medium", init, 1, "a Python package with no command")
        else:
            continue
        python_api(s, src, pkg, lits(exported.group(1)) if exported else None, exported)


def python_api(s, src, pkg, names, exported):
    code = src.code
    if names is None:
        names = [m.group(2) for m in re.finditer(r"^(def|class)\s+(\w+)", code, re.M)]
        for m in re.finditer(r"^from[ \t]+\.[\w.]*[ \t]+import[ \t]+(?:\(([^)]*)\)|([^\n]*))", code, re.M):
            names += [part.split(" as ")[-1].strip() for part in (m.group(1) or m.group(2)).split(",") if part.strip()]
    sources = [src] + [s.source(f) for f in s.files if f.startswith(pkg + "/") and f.endswith(".py") and f.count("/") == pkg.count("/") + 1]
    for name in names:
        kind, line, where = None, None, src.path
        for other in sources:
            if other is None:
                continue
            m = re.search(r"^(?:async\s+)?(def|class)\s+" + re.escape(name) + r"\b|^" + re.escape(name) + r"\s*[:=]", other.code, re.M)
            if m:
                kind = {"def": "function", "class": "class"}.get(m.group(1), "const")
                line, where = other.line(m.start()), other.path
                break
        if kind is None:
            kind = "class" if name[:1].isupper() and not name.isupper() else "const" if name.isupper() else "function"
            line = src.line(exported.start()) if exported else 1
        s.surface("api", {"name": name, "path": where, "line": line, "kind": kind})


WEB_APP_DEPS = {"next", "nuxt", "@sveltejs/kit", "@remix-run/react", "astro", "react-scripts", "@angular/core", "gatsby", "@vue/cli-service"}
TS_DECL = re.compile(r"^[ \t]*export\s+(?:declare\s+)?(?:default\s+)?(?:async\s+)?(function\*?|class|abstract\s+class|const|let|var|interface|type|enum|namespace)\s+([A-Za-z_$][\w$]*)", re.M)
TS_LIST = re.compile(r"^[ \t]*export\s+(type\s+)?\{([^}]*)\}(?:\s*from\s*['\"]([^'\"]+)['\"])?", re.M)
TS_STAR = re.compile(r"^[ \t]*export\s+\*(?:\s+as\s+(\w+))?\s+from\s*['\"]([^'\"]+)['\"]", re.M)
TS_KIND = {"function": "function", "function*": "function", "class": "class", "abstract class": "class", "const": "const",
           "let": "const", "var": "const", "interface": "type", "type": "type", "enum": "type", "namespace": "module"}
JS_EXTS = (".ts", ".tsx", ".mts", ".js", ".mjs", ".jsx", ".cjs")


def js_resolve(s, base, spec):
    stem = re.sub(r"\.(d\.ts|[cm]?[jt]sx?)$", "", posixpath.normpath(posixpath.join(base, spec)))
    for candidate in [stem + ext for ext in JS_EXTS] + [stem + "/index" + ext for ext in JS_EXTS]:
        if candidate in s.sizes:
            return candidate
    return None


def js_private(src, line):
    """True when the doc comment just above a declaration marks it internal."""
    above = []
    while line > 1 and len(above) < 30:
        line -= 1
        text = src.raw_line(line).strip()
        if not above and not text.endswith("*/"):
            break
        above.append(text)
        if text.startswith("/**") or text.startswith("/*"):
            break
    return any(re.search(r"@(internal|private|hidden)\b", t) for t in above)


def ts_api(s, rel, depth=0):
    src = s.source(rel)
    if src is None or depth > 2:
        return
    base = posixpath.dirname(rel)
    for m in TS_DECL.finditer(src.code):
        line = src.line(m.start())
        if not js_private(src, line):
            s.surface("api", {"name": m.group(2), "path": rel, "line": line, "kind": TS_KIND[" ".join(m.group(1).split())]})
    for m in TS_LIST.finditer(src.code):
        target = js_resolve(s, base, m.group(3)) if m.group(3) else rel
        tsrc = s.source(target) if target else None
        for part in m.group(2).split(","):
            words = part.split()
            if not words:
                continue
            # `type Foo` and `type Foo as Bar` mark a type; `type` alone or `type as x` is a binding named type.
            modifier = words[0] == "type" and len(words) in (2, 4) and words[1] != "as"
            is_type = bool(m.group(1)) or modifier
            words = words[1:] if modifier else words
            local, name = words[0], words[-1]
            if name == "default":
                continue
            kind = "type" if is_type else None
            line, where = src.line(m.start()), rel
            if tsrc is not None:
                d = re.search(r"\b(function\*?|class|const|let|var|interface|type|enum|namespace)\s+" + re.escape(local) + r"\b", tsrc.code)
                if d:
                    kind = kind or TS_KIND.get(d.group(1), "const")
                    if js_private(tsrc, tsrc.line(d.start())):
                        continue
            s.surface("api", {"name": name, "path": where, "line": line,
                              "kind": kind or ("class" if name[:1].isupper() else "function")})
    for m in TS_STAR.finditer(src.code):
        if m.group(1):
            s.surface("api", {"name": m.group(1), "path": rel, "line": src.line(m.start()), "kind": "module"})
        else:
            target = js_resolve(s, base, m.group(2))
            if target:
                ts_api(s, target, depth + 1)


def js_entry_modules(s, base, data):
    targets = []

    def collect(value):
        if isinstance(value, str):
            targets.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect(data.get("exports"))
    for key in ("module", "main", "types", "typings"):
        collect(data.get(key))
    found = []
    for target in targets:
        stem = re.sub(r"\.(d\.ts|[cm]?[jt]sx?)$", "", target[2:] if target.startswith("./") else target)
        for option in (stem, re.sub(r"^(dist|lib|build|out|esm|cjs|types)/", "src/", stem), "src/" + stem):
            hit = js_resolve(s, base, option)
            if hit and hit not in found:
                found.append(hit)
                break
    if not found:
        found = [p for p in (js_resolve(s, base, "src/index"), js_resolve(s, base, "index")) if p][:1]
    return found


def node_ecosystem(s):
    for m in manifests_of(s, "package.json"):
        path = m["path"]
        data, text, base = s.parsed.get(path) or {}, s.read(path), posixpath.dirname(path)
        deps = {}
        for key in ("dependencies", "peerDependencies", "optionalDependencies", "devDependencies"):
            if isinstance(data.get(key), dict):
                for dep in data[key]:
                    deps.setdefault(dep, key)
        line_of = lambda key: (find_line(text, r"^[ \t]*\"" + re.escape(key) + r"\"\s*:", default=None)  # noqa: E731
                               or find_line(text, r"\"" + re.escape(key) + r"\"\s*:"))
        for name in m["bins"]:
            s.entry(name, path, find_line(text, r"^[ \t]*\"" + re.escape(name) + r"\"\s*:", r"\"bin\"") if isinstance(data.get("bin"), dict) else line_of("bin"), "package.json bin")
        engines = data.get("engines") if isinstance(data.get("engines"), dict) else {}
        private = data.get("private") is True
        if m["name"] and not private and "vscode" not in engines:
            s.channel("npm", m["name"], path, line_of("name"))
        contributes = data.get("contributes") if isinstance(data.get("contributes"), dict) else {}
        if "vscode" in engines:
            s.kind("extension", "editor-extension", "high", path, line_of("vscode"), "engines.vscode names the editor")
            s.channel("vscode-marketplace", data.get("publisher") and f"{data['publisher']}.{m['name']}", path, line_of("engines"))
            if "ovsx" in json.dumps(data.get("scripts") or {}):
                s.channel("open-vsx", m["name"], path, find_line(text, "ovsx"))
            for cmd in contributes.get("commands") or []:
                if isinstance(cmd, dict) and _str(cmd.get("command")):
                    s.surface("commands", {"name": cmd["command"], "path": path, "description": _str(cmd.get("title")),
                                           "line": find_line(text, r"\"command\"\s*:\s*\"" + re.escape(cmd["command"]) + "\"")},
                              manifest=True)
            conf = contributes.get("configuration")
            for block in conf if isinstance(conf, list) else [conf] if isinstance(conf, dict) else []:
                if isinstance(block.get("properties"), dict):
                    s.surfaces["config"].append({"path": path, "keys": list(block["properties"])})
        if "electron" in deps:
            s.kind("app", "desktop", "high", path, line_of("electron"), "depends on Electron")
        if "react-native" in deps:
            s.kind("app", "mobile", "high", path, line_of("react-native"), "depends on React Native")
        web = sorted(WEB_APP_DEPS & set(deps)) or (["vite"] if "vite" in deps and js_resolve(s, base, "index.html") is None
                                                     and posixpath.join(base, "index.html") in s.sizes else [])
        if web and not data.get("exports"):
            s.kind("app", "web", "medium", path, line_of(web[0]), f"depends on {web[0]}")
            s.platform("web", path, line_of(web[0]))
        for tui in ("ink", "blessed", "neo-blessed"):
            if deps.get(tui) == "dependencies" and m["bins"]:
                s.kind("terminal", "tui", "medium", path, line_of(tui), f"depends on {tui}")
        if isinstance(data.get("os"), list):
            for os_name in data["os"]:
                if not isinstance(os_name, str):
                    s.malformed(path, "os holds a value that is not a string")
                    continue
                plat = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(os_name)
                if plat:
                    s.platform(plat, path, line_of("os"))
        if private or (web and not data.get("exports")) or "electron" in deps or "vscode" in engines:
            continue  # an app, not a library; explicit exports make it a library whatever builds it
        if data.get("exports"):
            s.kind("library", None, "high", path, line_of("exports"), "package.json exports modules")
        elif (data.get("main") or data.get("module") or data.get("types")) and not m["bins"] and not s.flags["mcp"]:
            key = "main" if data.get("main") else "module" if data.get("module") else "types"
            s.kind("library", None, "medium", path, line_of(key), f"package.json names a {key} module")
        else:
            continue
        for entry in js_entry_modules(s, base, data):
            ts_api(s, entry)


def rust_ecosystem(s):
    for m in manifests_of(s, "Cargo.toml"):
        path, data, text = m["path"], s.parsed.get(m["path"]) or {}, s.read(m["path"])
        base = posixpath.dirname(path)
        pkg = data.get("package") if isinstance(data.get("package"), dict) else {}  # read_cargo noted any other shape
        deps = set(_table(s, path, data.get("dependencies"), "dependencies"))
        for name in m["bins"]:
            via = "Cargo [[bin]]" if re.search(r"^[ \t]*name\s*=\s*\"" + re.escape(name) + "\"", text.split("[[bin]]", 1)[-1], re.M) and "[[bin]]" in text else "Cargo src/main.rs" if name == pkg.get("name") else "Cargo src/bin"
            s.entry(name, path, find_line(text, r"^[ \t]*name\s*=\s*\"" + re.escape(name) + "\"", r"^\[\[bin\]\]") if via == "Cargo [[bin]]" else 1, via)
        lib = data.get("lib") if isinstance(data.get("lib"), dict) else None
        lib_path = posixpath.normpath(posixpath.join(base, _str((lib or {}).get("path")) or "src/lib.rs"))
        if lib is not None or lib_path in s.sizes:
            s.kind("library", None, "high", path if lib is not None else lib_path, find_line(text, r"^\[lib\]") if lib is not None else 1,
                   "Cargo.toml has a [lib] target" if lib is not None else "src/lib.rs is a library crate")
            rust_api(s, lib_path)
        if pkg.get("name") and pkg.get("publish") is not False:
            s.channel("crates", pkg["name"], path, find_line(text, r"^[ \t]*name\s*=", r"^\[package\]"))
        for dep, kind, sub, why in (("ratatui", "terminal", "tui", "ratatui"), ("cursive", "terminal", "tui", "cursive"),
                                    ("tauri", "app", "desktop", "Tauri"), ("eframe", "app", "desktop", "eframe"),
                                    ("iced", "app", "desktop", "iced"), ("gtk4", "app", "desktop", "GTK 4"),
                                    ("slint", "app", "desktop", "Slint"), ("relm4", "app", "desktop", "Relm4")):
            if dep in deps and (kind == "app" or m["bins"]):
                s.kind(kind, sub, "medium", path, find_line(text, r"^[ \t]*" + dep + r"\s*="), f"depends on {why}")


def rust_api(s, rel):
    src = s.source(rel)
    if src is None:
        return
    for m in re.finditer(r"^pub\s+(?:async\s+)?(?:unsafe\s+)?(?:const\s+(?=fn))?(fn|struct|enum|trait|type|const|static|mod|union)\s+(\w+)", src.code, re.M):
        line = src.line(m.start())
        if "doc(hidden)" in src.raw_line(line - 1):
            continue
        kind = {"fn": "function", "struct": "class", "enum": "type", "trait": "type", "type": "type", "union": "type", "mod": "module"}.get(m.group(1), "const")
        s.surface("api", {"name": m.group(2), "path": rel, "line": line, "kind": kind})
    for m in re.finditer(r"^pub\s+use\s+([^;]+);", src.code, re.M):
        for name in re.findall(r"(\w+)\s*(?=[,}]|$)", m.group(1).replace("\n", " ")):
            if name not in ("self", "crate", "super"):
                s.surface("api", {"name": name, "path": rel, "line": src.line(m.start()), "kind": "class" if name[:1].isupper() else "function"})


def go_ecosystem(s):
    for m in manifests_of(s, "go.mod"):
        path, module = m["path"], m["name"]
        base = posixpath.dirname(path)
        if module:
            s.channel("go", module, path, 1)
        packages = {}
        for rel in s.files:
            if rel.endswith(".go") and not rel.endswith("_test.go") and s.product(rel) and (not base or rel.startswith(base + "/")):
                src = s.source(rel)
                pkg = re.search(r"^package\s+(\w+)", src.code, re.M) if src else None
                if pkg:
                    packages.setdefault(posixpath.dirname(rel), []).append((pkg.group(1), src))
        for folder, files in sorted(packages.items()):
            if any(p == "main" and re.search(r"^func\s+main\(\)", f.code, re.M) for p, f in files):
                main = next(f for p, f in files if p == "main" and re.search(r"^func\s+main\(\)", f.code, re.M))
                name = posixpath.basename(folder) if folder != base else (module or "main").rsplit("/", 1)[-1]
                s.entry(name, main.path, find_line(main.code, r"^func\s+main\("), "main.go")
            elif "internal" not in folder.split("/") and all(p != "main" for p, _ in files):
                s.kind("library", None, "high" if folder == base else "medium", files[0][1].path, 1, f"Go package {files[0][0]}")
                for _, f in files:
                    for d in re.finditer(r"^(?:func\s+([A-Z]\w*)\s*[\[(]|type\s+([A-Z]\w*)\s|(?:const|var)\s+([A-Z]\w*)\b)", f.code, re.M):
                        kind = "function" if d.group(1) else "type" if d.group(2) else "const"
                        s.surface("api", {"name": d.group(1) or d.group(2) or d.group(3), "path": f.path, "line": f.line(d.start()), "kind": kind})


def desktop_ecosystem(s):
    for rel in s.files:
        if rel.endswith(".desktop") and s.product(rel):
            text = s.read(rel) or ""
            if re.search(r"^Type\s*=\s*Application\s*$", text, re.M):
                s.kind("app", "desktop", "high", rel, find_line(text, r"^Type\s*="), "a .desktop launcher entry")
                s.platform("linux", rel, 1)
                exe = re.search(r"^Exec\s*=\s*(\S+)", text, re.M)
                if exe:
                    s.entry(posixpath.basename(exe.group(1).strip("\"'")), rel, find_line(text, r"^Exec\s*="), ".desktop", cli=False)
    qml = [f for f in s.files if f.endswith(".qml") and s.product(f)]
    for m in manifests_of(s, "*.pro", "CMakeLists.txt", "meson.build"):
        text = s.read(m["path"]) or ""
        gui = re.search(r"^[ \t]*QT\s*\+?=.*\b(quick|widgets|qml)\b|Qt[56]?::(?:Quick|Widgets|Qml)\b|find_package\(\s*Qt[56].*\b(?:Quick|Widgets)\b|dependency\(\s*'(?:gtk4|gtk\+-3\.0|libadwaita-1)'", text, re.M)
        if gui:
            s.kind("app", "desktop", "high" if m["type"] == "*.pro" else "medium", m["path"], text.count("\n", 0, gui.start()) + 1, f"links {gui.group(0).strip()[:40]}")
        for name in m["bins"]:
            s.entry(name, m["path"], find_line(text, re.escape(name)), {"*.pro": "qmake TARGET", "CMakeLists.txt": "CMake add_executable", "meson.build": "meson executable"}[m["type"]], cli=not gui)
    if qml:
        s.kind("app", "desktop", "medium", qml[0], 1, "Qt Quick (QML) interface")
    for m in manifests_of(s, "PKGBUILD"):
        text = s.read(m["path"]) or ""
        for name in m["bins"]:
            s.entry(name, m["path"], find_line(text, r"/usr/bin/" + re.escape(name) + r"(?![\w.+-])"), "PKGBUILD", cli=False)
        s.channel("aur" if manifests_of(s, ".SRCINFO") else "pacman", m["name"], m["path"], find_line(text, r"^pkgname="))
        s.platform("linux", m["path"], find_line(text, r"^arch="))
        if re.search(r"wayland", text):
            s.platform("wayland", m["path"], find_line(text, r"wayland"))
    for rel in s.files:
        name = rel.rsplit("/", 1)[-1]
        if not s.product(rel):
            continue
        if name == "tauri.conf.json":
            s.kind("app", "desktop", "high", rel, 1, "a Tauri app")
        elif name == "AndroidManifest.xml":
            s.kind("app", "mobile", "high", rel, 1, "an Android manifest")
            s.platform("android", rel, 1)
        elif name == "hyprpm.toml":
            s.kind("extension", "compositor-plugin", "high", rel, 1, "a Hyprland plugin (hyprpm.toml)")
            s.platform("hyprland", rel, 1)
        elif name in ("snapcraft.yaml",):
            s.channel("snap", None, rel, 1)
        elif re.match(r"[a-z]+\.[\w-]+\.[\w.-]+\.(ya?ml|json)$", name, re.I) and re.search(r"^[ \t]*[\"']?app-id[\"']?\s*:", s.read(rel) or "", re.M):
            s.channel("flatpak", name.rsplit(".", 1)[0], rel, find_line(s.read(rel), r"app-id"))
    for rel in s.code_files("C", "C++", "Lua"):
        src = s.source(rel)
        plugin = src and re.search(r"#\s*include\s*[<\"]hyprland/src/", src.code)
        module = src and src.lang == "Lua" and re.search(r"\bhl\.(?:dispatch|bind|config|on|get_windows)\s*\(", src.code)
        if plugin:
            s.kind("extension", "compositor-plugin", "high", rel, src.line(plugin.start()), "includes Hyprland's plugin headers")
        elif module:
            s.kind("extension", "compositor-plugin", "medium", rel, src.line(module.start()), "a Lua module for Hyprland's configuration (hl.* calls)")
        if plugin or module:
            s.platform("hyprland", rel, src.line((plugin or module).start()))
    for rel in s.code_files("C", "C++", "QML", "Python", "Rust", "Go", "JavaScript", "TypeScript", "Shell", "Lua"):
        src = s.source(rel)
        hit = src and re.search(r"\bhyprctl\b|HYPRLAND_INSTANCE_SIGNATURE", src.code)
        if hit:
            s.platform("hyprland", rel, src.line(hit.start()))
            break


AGENT_PLUGIN_DIRS = {".codex-plugin", ".cursor-plugin", ".grok-plugin", ".antigravity-plugin"}


def agent_ecosystem(s):
    for m in manifests_of(s, "SKILL.md"):
        data = s.parsed.get(m["path"]) or {}
        name = m["name"] or posixpath.basename(posixpath.dirname(m["path"])) or None
        s.kind("extension", "agent-skill", "high", m["path"], 1, "SKILL.md with frontmatter" if data else "a SKILL.md file")
        line = find_line(s.read(m["path"]) or "", r"^name\s*:") if m["name"] else 1
        s.surface("skills", {"name": name, "path": m["path"], "line": line, "description": m["description"]}, manifest=True)
        s.channel("gh-skill", name if len(manifests_of(s, "SKILL.md")) == 1 else None, m["path"], 1)
    plugin_dirs = []
    for m in manifests_of(s, "plugin.json", "gemini-extension.json") + manifests_of(s, "marketplace.json"):
        path, data = m["path"], s.parsed.get(m["path"]) or {}
        folder = posixpath.dirname(path)
        top = folder.rsplit("/", 1)[-1]
        agentish = any(k in data for k in ("skills", "commands", "agents", "hooks", "mcpServers", "plugins")) or "plugin" in str(data.get("$schema", ""))
        if top == ".claude-plugin":
            s.channel("claude-plugin", m["name"], path, 1)
        elif m["type"] == "gemini-extension.json" or top in AGENT_PLUGIN_DIRS or (m["type"] == "plugin.json" and agentish):
            s.channel("agent-plugin", m["name"], path, 1)
        else:
            continue
        if m["type"] != "marketplace.json":
            s.kind("extension", "agent-plugin", "high", path, 1, f"{path} declares a plugin")
            plugin_dirs.append(posixpath.dirname(folder) if top.startswith(".") else folder)
        if isinstance(data.get("userConfig"), dict):
            s.surfaces["config"].append({"path": path, "keys": list(data["userConfig"])})
        if isinstance(data.get("hooks"), dict):
            agent_hooks(s, path, data["hooks"])
    for base in dict.fromkeys(plugin_dirs + [".claude"]):
        prefix = base + "/" if base else ""
        hooks = prefix + "hooks/hooks.json"
        if hooks in s.sizes and base != ".claude":
            data = formats.parse_json(s.read(hooks) or "")
            if isinstance(data, dict):
                agent_hooks(s, hooks, data.get("hooks") if isinstance(data.get("hooks"), dict) else data)
        for rel in s.files:
            if rel.startswith(prefix + "commands/") and rel.endswith(".md"):
                fm, _, _ = formats.frontmatter(s.read(rel) or "")
                name = rel[len(prefix + "commands/"):-3].replace("/", ":")
                s.surface("commands", {"name": name, "path": rel, "line": 1, "description": _str((fm or {}).get("description"))},
                          manifest=True)  # the file is the declaration
    for m in manifests_of(s, "manifest.json"):
        data = s.parsed.get(m["path"]) or {}
        if "manifest_version" in data:
            s.kind("extension", "browser-extension", "high", m["path"], find_line(s.read(m["path"]), r"\"manifest_version\""), "a browser extension manifest")
            s.channel("chrome-web-store", m["name"], m["path"], 1)
            s.platform("web", m["path"], 1)
        elif "minAppVersion" in data:
            s.kind("extension", "editor-extension", "medium", m["path"], find_line(s.read(m["path"]), r"\"minAppVersion\""), "an Obsidian plugin manifest")
    if any(f.startswith("lua/") and f.endswith(".lua") for f in s.files) and any(f.startswith("plugin/") for f in s.files):
        s.kind("extension", "editor-extension", "medium", next(f for f in s.files if f.startswith("plugin/")), 1, "a Neovim plugin layout (lua/ and plugin/)")
    if s.flags["mcp"]:
        path, line = s.flags["mcp_at"]
        if s.surfaces["tools"]:
            tool = s.surfaces["tools"][0]
            s.kind("extension", "mcp-server", "high", tool["path"], tool["line"], "registers MCP tools")
        s.kind("extension", "mcp-server", "medium", path, line, "imports an MCP server SDK")


def agent_hooks(s, path, hooks):
    text = s.read(path) or ""
    for event in hooks:
        s.surface("hooks", {"event": event, "path": path, "line": find_line(text, r"\"" + re.escape(event) + r"\"\s*:")}, manifest=True)


SENSITIVE_INPUT_RE = re.compile(r"token|secret|password|passwd|key|credential", re.I)


def action_surface(path, text):
    """An action.yml's name, inputs, outputs and runner; certain is False when the YAML was not read cleanly."""
    data, certain = formats.read_yaml(text)
    data = data if isinstance(data, dict) else {}
    runs = data.get("runs") if isinstance(data.get("runs"), dict) else {}

    def flag(v):
        return {"true": True, "false": False}.get(str(v).lower()) if v is not None else None

    def default(name, v):  # a default for a token, password or key is shown as set, never as its value
        if not isinstance(v, dict) or v.get("default") is None:
            return None
        return "(set, hidden)" if SENSITIVE_INPUT_RE.search(str(name)) else str(v.get("default"))

    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
    return {
        "path": path, "name": _str(data.get("name")), "description": _str(data.get("description")),
        "inputs": {str(k): {"required": flag((v or {}).get("required")) if isinstance(v, dict) or v is None else None,
                            "default": default(k, v),
                            "description": _str(v.get("description")) if isinstance(v, dict) else None} for k, v in inputs.items()},
        "outputs": {str(k): {"description": _str(v.get("description")) if isinstance(v, dict) else None} for k, v in outputs.items()},
        "runs": _str(runs.get("using")), "certain": certain}


def automation_ecosystem(s):
    for m in manifests_of(s, "action.yml"):
        text = s.read(m["path"]) or ""
        s.kind("automation", "github-action", "high", m["path"], find_line(text, r"^runs\s*:"), "action.yml defines a GitHub Action")
        if s.surfaces["action"] is None and "/" not in m["path"]:
            s.surfaces["action"] = action_surface(m["path"], text)  # the root Action; check_readme reads nested ones by path
    if ".pre-commit-hooks.yaml" in s.sizes:
        text = s.read(".pre-commit-hooks.yaml") or ""
        data, _ = formats.read_yaml(text)
        s.kind("automation", "pre-commit-hook", "high", ".pre-commit-hooks.yaml", 1, "declares pre-commit hooks")
        for hook in data if isinstance(data, list) else []:
            if isinstance(hook, dict) and _str(hook.get("id")):
                stages = hook.get("stages")
                s.surface("hooks", {"event": stages[0] if isinstance(stages, list) and stages else "pre-commit", "name": hook["id"],
                                    "path": ".pre-commit-hooks.yaml", "line": find_line(text, r"id:\s*['\"]?" + re.escape(hook["id"]))}, manifest=True)
    for rel in s.files:
        if not (rel.startswith(".github/workflows/") and rel.endswith((".yml", ".yaml"))):
            continue
        text = s.read(rel) or ""
        data, _ = formats.read_yaml(text)
        on = data.get("on") if isinstance(data, dict) else None
        if on == "workflow_call" or (isinstance(on, (dict, list)) and "workflow_call" in on):
            s.kind("automation", "reusable-workflow", "high", rel, find_line(text, r"workflow_call"), "on: workflow_call")
        for pattern, channel in ((r"softprops/action-gh-release|goreleaser|gh release (?:create|upload)|ncipollo/release-action", "release-assets"),
                                 (r"docker/build-push-action|docker push", "docker"), (r"Homebrew|brew tap|homebrew-", "brew"),
                                 (r"winget", "winget"), (r"\bscoop\b", "scoop"), (r"\bovsx\b|open-vsx", "open-vsx"),
                                 (r"vsce publish|HaaLeo/publish-vscode-extension", "vscode-marketplace")):
            hit = re.search(pattern, text)
            if hit:
                s.channel(channel, None, rel, text.count("\n", 0, hit.start()) + 1)


def service_ecosystem(s):
    for m in manifests_of(s, "Dockerfile"):
        text = s.read(m["path"]) or ""
        expose = re.search(r"^[ \t]*EXPOSE\s+(\d+)", text, re.M | re.I)
        if expose:
            s.kind("service", "web", "medium", m["path"], text.count("\n", 0, expose.start()) + 1, f"EXPOSE {expose.group(1)}")
        for env in re.finditer(r"^[ \t]*ENV\s+(.+)$", text, re.M | re.I):
            for name in re.findall(r"(?:^|\s)([A-Z_][A-Z0-9_]*)(?==|\s|$)", env.group(1))[:1] + re.findall(r"\s([A-Z_][A-Z0-9_]*)=", env.group(1)):
                s.surface("env", {"name": name, "path": m["path"], "line": text.count("\n", 0, env.start()) + 1}, manifest=True)
        s.channel("docker", None, m["path"], 1)
    for m in manifests_of(s, "compose"):
        text = s.read(m["path"]) or ""
        services = (s.parsed.get(m["path"]) or {}).get("services")
        for name, svc in (services.items() if isinstance(services, dict) else []):
            if not isinstance(svc, dict):
                continue
            if svc.get("ports") and (svc.get("build") or not manifests_of(s, "Dockerfile")):
                s.kind("service", "web", "high", m["path"], find_line(text, r"^[ \t]*ports\s*:", r"^[ \t]*" + re.escape(str(name)) + r"\s*:"), f"compose service {name} publishes ports")
            env = svc.get("environment")
            names = list(env) if isinstance(env, dict) else [str(e).split("=", 1)[0] for e in env] if isinstance(env, list) else []
            for var in names:
                if re.match(r"[A-Z_][A-Z0-9_]*$", str(var)):
                    s.surface("env", {"name": var, "path": m["path"], "line": find_line(text, r"\b" + re.escape(var) + r"\b")}, manifest=True)
        s.channel("docker", None, m["path"], 1)
    for rel in s.files:
        if rel.rsplit("/", 1)[-1].lower() in (".env.example", ".env.sample") and s.product(rel):
            for i, line in enumerate((s.read(rel) or "").split("\n"), 1):
                var = re.match(r"\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=", line)
                if var:
                    s.surface("env", {"name": var.group(1), "path": rel, "line": i}, manifest=True)
    if s.surfaces["routes"]:
        route = s.surfaces["routes"][0]
        s.kind("service", "web", "high", route["path"], route["line"], f"serves {route['method']} {route['route']}")
    for f in ("install.sh", "bin/install", "scripts/install.sh", "install"):
        if f in s.sizes:
            s.channel("source", None, f, 1)
    for m in manifests_of(s, "Makefile"):
        if "install" in m["scripts"] and "/" not in m["path"]:
            s.channel("source", None, m["path"], find_line(s.read(m["path"]), r"^install\s*:"))


# ---------------------------------------------------------------- docs, pictures, history

LICENSES = (
    ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE\s+Version 3"), ("LGPL-3.0", r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 3"),
    ("LGPL-2.1", r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 2\.1"), ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
    ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"), ("Apache-2.0", r"Apache License,?\s+Version 2\.0"),
    ("MPL-2.0", r"Mozilla Public License,?\s+(?:Version|v\.)\s*2\.0"), ("MIT", r"Permission is hereby granted, free of charge"),
    ("BSD-3-Clause", r"Neither the name of"), ("BSD-2-Clause", r"Redistributions in binary form"),
    ("ISC", r"Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted, provided"),
    ("0BSD", r"Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee"),
    ("Unlicense", r"This is free and unencumbered software"),
)


README_NAMES = ("readme.md", "readme.rst", "readme.txt", "readme", "readme.markdown", "readme.adoc")


def root_readme(files):
    """The README at the root of a file list, or None."""
    root = {f.lower(): f for f in files if "/" not in f}
    return next((root[n] for n in README_NAMES if n in root), None)


def scan_docs(s):
    root = {f.lower(): f for f in s.files if "/" not in f}
    pick = lambda *names: next((root[n] for n in names if n in root), None)  # noqa: E731
    lower = {f.lower(): f for f in s.files}
    docs = {
        "readme": root_readme(s.files),
        "guide": next((lower[n] for n in ("docs/guide.md", "docs/user-guide.md", "docs/usage.md", "guide.md", "docs/getting-started.md") if n in lower), None),
        "changelog": pick("changelog.md", "changes.md", "history.md", "news.md", "changelog", "changelog.rst", "changes.rst"),
        "contributing": pick("contributing.md") or lower.get(".github/contributing.md") or lower.get("docs/contributing.md"),
        "license": {"path": pick("license", "license.md", "license.txt", "licence", "licence.md", "copying", "copying.md"), "spdx": None},
        "docs_dir": [f for f in s.files if f.startswith("docs/") and f.endswith((".md", ".rst", ".adoc", ".txt", ".mdx"))][:100],
    }
    if docs["license"]["path"]:
        text = s.read(docs["license"]["path"]) or ""
        spdx = re.search(r"SPDX-License-Identifier:\s*([\w.+-]+)", text)
        docs["license"]["spdx"] = spdx.group(1) if spdx else next((sid for sid, p in LICENSES if re.search(p, text, re.I)), None)
    if not docs["license"]["spdx"]:
        docs["license"]["spdx"] = next((m["license"] for m in s.manifests if m["license"] and re.match(r"[\w.+-]+$", m["license"])), None)
    scripts = [f for f in s.files if (f.split("/")[0] in ("bin", "scripts", "tools") and re.search(r"screenshot|capture|demo|record", f.rsplit("/", 1)[-1], re.I))
               or f.endswith(".tape")]
    examples = sorted({"/".join(f.split("/")[:2]) for f in s.files if f.split("/")[0] in EXAMPLE_DIRS and "/" in f})
    test_dirs = sorted({"/".join(f.split("/")[:i + 1]) for f in s.files for i, part in enumerate(f.split("/")[:-1]) if part in TEST_DIRS
                        and not any(p in TEST_DIRS for p in f.split("/")[:i])})
    rules = [f for f in s.files if f.rsplit("/", 1)[-1] in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "CONVENTIONS.md", "copilot-instructions.md")
             and not s.is_test(f)][:20]
    return docs, {"images": [i for i in s.images if not s.is_test(i["path"])], "scripts": scripts}, examples, \
        {"files": sum(1 for f in s.files if s.is_test(f) and f in s.sizes), "dirs": test_dirs}, rules


# A repository's own config can name programs for git to run (fsmonitor, hooks, signature
# checks, external diffs, pagers, transports, credential and password helpers, editors) and
# files for it to read (an order file, ignore and attribute files); these overrides switch every
# one of them off.
GIT_SAFE = (
    "--no-pager",
    "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull, "-c", "log.showSignature=false",
    "-c", "gpg.program=false", "-c", "diff.external=", "-c", "core.pager=cat",
    "-c", "protocol.allow=never", "-c", "core.sshCommand=false", "-c", "credential.helper=",
    "-c", "core.askPass=false", "-c", "core.editor=false", "-c", "core.alternateRefsCommand=false",
    "-c", "uploadpack.packObjectsHook=false", "-c", "gc.auto=0",
    "-c", "core.excludesFile=" + os.devnull, "-c", "core.attributesFile=" + os.devnull,
    "-c", "diff.orderFile=" + os.devnull, "-c", "core.quotePath=true",  # an empty orderFile is an error
)
GIT_TIMEOUT = 10  # seconds per command at most
GIT_DEADLINE = 30  # seconds for the whole history: the checks of .git, then every command
GIT_OUTPUT_LIMIT = 4 * 1024 * 1024  # bytes of output per command; more is treated as a failure
GIT_ENTRY_LIMIT = 50000  # entries of .git examined for symlinks; a larger .git is not read
GIT_CONFIG_LIMIT = 1024 * 1024  # bytes of git config read, includes and all


def history_blocker(tree, deadline):
    """Why git must not read this repository, or None.

    Git runs only on a .git folder whose data all lies inside the root: not a
    symlink or a "gitdir:" file (linked worktrees, submodules), no symlink
    anywhere in it, no shared commondir or borrowed objects, no config
    include that leads outside, and not a partial clone (whose missing
    objects git would fetch). These checks have their own limits on entries,
    bytes and time; past one, history is not read.
    """
    git_dir = os.path.join(tree.abs, ".git")
    if os.path.islink(git_dir):
        return ".git is a symlink"
    if not os.path.isdir(git_dir):
        return ".git is a file that points to a repository elsewhere"
    why = git_dir_blocker(tree, deadline)
    if why:
        return why
    if os.path.lexists(os.path.join(git_dir, "commondir")):
        return ".git/commondir shares another repository's data"
    if os.path.lexists(os.path.join(git_dir, "objects", "info", "alternates")):
        return ".git/objects/info/alternates borrows objects from elsewhere"
    return config_blocker(tree, deadline)


def git_dir_blocker(tree, deadline):
    """Why the .git folder cannot be confined (a symlink in it, too many entries, too slow), or None."""
    queue, seen = deque([".git"]), 0
    while queue:
        rel = queue.popleft()
        try:
            with tree.scandir(rel) as it:
                for entry in it:
                    seen += 1
                    if seen > GIT_ENTRY_LIMIT:
                        return f".git has more than {GIT_ENTRY_LIMIT} entries, too many to check"
                    kind = entry_kind(entry)[0]
                    if kind == "symlink":
                        return f"{rel}/{entry.name} is a symlink"
                    if kind == "dir":
                        queue.append(f"{rel}/{entry.name}")
                    elif entry.name.endswith(".promisor"):
                        return "the repository is a partial clone, whose missing objects git would fetch"
        except OSError:
            return f"{rel} cannot be listed"
        if time.monotonic() > deadline:
            return "checking .git took too long"
    return None


_GIT_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
_GIT_ESCAPES = {"t": "\t", "b": "\b", "n": "\n", '"': '"', "\\": "\\"}


def git_config_entries(text):
    """(section, key, value) for each variable in git config text, read the way git reads it.

    section is lowercased, with any subsection after a dot; value is None for
    a bare key (git reads it as true). Quotes, escapes and lines continued by
    a final backslash are all followed. Raises ValueError for text git would
    refuse.
    """
    i, n, section, out = 0, len(text), "", []
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "#;":
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c == "[":
            m = re.compile(r'\[([A-Za-z0-9.-]+)(?:\s+"((?:[^"\\\n]|\\.)*)")?\]').match(text, i)
            if not m:
                raise ValueError("bad section header")
            section = m.group(1).lower() + ("." + re.sub(r"\\(.)", r"\1", m.group(2)) if m.group(2) is not None else "")
            i = m.end()
        else:
            m = _GIT_NAME_RE.match(text, i)
            if not m:
                raise ValueError("bad config line")
            key, i = m.group(0).lower(), m.end()
            while i < n and text[i] in " \t":
                i += 1
            value = None
            if i < n and text[i] == "=":
                value, i = _git_value(text, i + 1)
            elif i < n and text[i] not in "\n#;":
                raise ValueError("bad config line")
            out.append((section, key, value))
    return out


def _git_value(text, i):
    """A config value from text[i] to the end of its (possibly continued) line, and where it ends."""
    out, quote, comment, spaces, n = [], False, False, 0, len(text)
    while i < n:
        c = text[i]
        i += 1
        if c == "\n":
            if quote:
                raise ValueError("unclosed quote")
            return "".join(out), i
        if comment:
            continue
        if c in " \t" and not quote:
            spaces += 1 if out else 0
            continue
        if not quote and c in "#;":
            comment = True
            continue
        out.append(" " * spaces)
        spaces = 0
        if c == "\\":
            if i >= n:
                raise ValueError("backslash at the end")
            c, i = text[i], i + 1
            if c == "\n":
                continue
            if c not in _GIT_ESCAPES:
                raise ValueError("bad escape")
            out.append(_GIT_ESCAPES[c])
        elif c == '"':
            quote = not quote
        else:
            out.append(c)
    if quote:
        raise ValueError("unclosed quote")
    return "".join(out), i


def config_blocker(tree, deadline):
    """Why git's config cannot be confined, or None.

    .git/config and .git/config.worktree are read with every file they
    include, each once, up to GIT_CONFIG_LIMIT bytes in all. An include that
    leads outside the root (or to a secrets file), config that cannot be
    read or parsed, and a partial clone each stop git.
    """
    budget = [GIT_CONFIG_LIMIT]
    seen = set()
    queue = deque((".git/" + name, 0) for name in ("config", "config.worktree"))
    while queue:
        rel, depth = queue.popleft()
        if rel in seen:
            continue
        seen.add(rel)
        if time.monotonic() > deadline:
            return "checking git's config took too long"
        if not os.path.lexists(os.path.join(tree.abs, *rel.split("/"))):
            continue  # git skips an include that does not exist
        if depth > 10:
            return f"{rel} is included too deeply to check"
        git_data = rel.startswith(".git/")
        data = tree.read_bytes(rel, budget[0] + 1, follow=False, git_data=git_data)
        if data is None:
            return f"{rel} cannot be read to check it"
        if len(data) > budget[0]:
            return "git's config is too large to check"
        budget[0] -= len(data)
        try:
            entries = git_config_entries(safety.decode_text(data, len(data)) or "")
        except ValueError:
            return f"{rel} cannot be parsed"
        for section, key, value in entries:
            top = section.split(".", 1)[0]
            if ((section, key) == ("extensions", "partialclone") and value) or \
                    (top == "remote" and key == "promisor" and (value is None or value.lower() in ("true", "yes", "on", "1"))):
                return "the repository is a partial clone, whose missing objects git would fetch"
            if top not in ("include", "includeif") or key != "path" or not value:
                continue
            if value.startswith(("~", "%(")):
                return f"{rel} includes a file outside the root"
            target = os.path.realpath(os.path.join(os.path.dirname(os.path.join(tree.abs, *rel.split("/"))), value))
            if not tree.inside(target):
                return f"{rel} includes a file outside the root"
            queue.append((os.path.relpath(target, tree.abs).replace(os.sep, "/"), depth + 1))
    return None


def _under(path, folder):
    return bool(folder) and (path == folder or path.startswith(folder.rstrip(os.sep) + os.sep))


def _cwd():
    try:
        return os.path.realpath(os.getcwd())
    except OSError:
        return None


def trusted_path(root):
    """PATH folders that are absolute and lie outside both the root and the working folder, and below them."""
    cwd = _cwd()
    keep = []
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if not folder or not os.path.isabs(folder):
            continue
        real = os.path.realpath(folder)
        if _under(real, root) or _under(real, cwd):
            continue
        keep.append(folder)
    return keep


def find_git(folders, root=None):
    """The resolved path of the first git program in folders that lies outside root and the working folder, or None.

    The program itself is resolved, so a link in a trusted folder to a file in
    the project is not run, and what runs is the file that was checked.
    """
    names = ("git.exe", "git") if os.name == "nt" else ("git",)
    cwd = _cwd()
    for folder in folders:
        for name in names:
            exe = os.path.join(folder, name)
            if os.path.isfile(exe) and os.access(exe, os.X_OK):
                real = os.path.realpath(exe)
                if (root and _under(real, root)) or _under(real, cwd):
                    continue
                return real
    return None


def git_env(root, home):
    """The environment git runs in: this repository only, no outside config, no fetching or prompts."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    if os.name != "nt":  # a minimal environment; Windows programs need more of theirs
        env = {k: v for k, v in env.items() if k in ("LANG", "TZ")}
    env.update(PATH=os.pathsep.join(trusted_path(root)), HOME=home, XDG_CONFIG_HOME=home, LC_ALL="C",
               GIT_DIR=os.path.join(root, ".git"), GIT_WORK_TREE=root, GIT_CEILING_DIRECTORIES=os.path.dirname(root),
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_NO_LAZY_FETCH="1",
               GIT_ALLOW_PROTOCOL="", GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_ASK_YESNO="false",
               GIT_PAGER="cat")
    return env


def run_git(exe, root, env, args, deadline=None):
    """Output of one git command, or None if it fails, times out, or prints more than GIT_OUTPUT_LIMIT.

    It may run GIT_TIMEOUT seconds, and no later than the deadline."""
    timeout = GIT_TIMEOUT if deadline is None else min(GIT_TIMEOUT, deadline - time.monotonic())
    if timeout <= 0:
        return None
    try:
        proc = subprocess.Popen([exe, *GIT_SAFE, "-C", root, *args], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    except (OSError, ValueError):
        return None
    out = []
    reader = threading.Thread(target=lambda: out.append(proc.stdout.read(GIT_OUTPUT_LIMIT + 1)), daemon=True)
    reader.start()
    reader.join(timeout)
    timed_out = reader.is_alive()
    if proc.poll() is None:  # still running: timed out, or stopped at the output limit
        proc.kill()
    reader.join()
    proc.wait()
    proc.stdout.close()
    data = out[0] if out else b""
    if timed_out or proc.returncode != 0 or len(data) > GIT_OUTPUT_LIMIT:
        return None
    return data.decode("utf-8", "replace")


def git_history(s, since):
    h = s.history
    if not os.path.lexists(os.path.join(s.root, ".git")):
        if since:
            h["since_error"] = "no git repository at the root"
        return
    deadline = time.monotonic() + GIT_DEADLINE
    reason = history_blocker(s.tree, deadline)
    exe = None if reason else find_git(trusted_path(s.root), s.root)
    if not reason and not exe:
        reason = "no git program outside the project and the working folder was found on PATH"
    home = None
    if not reason:
        try:
            home = tempfile.TemporaryDirectory(prefix="discover-git-", ignore_cleanup_errors=True)
        except OSError as err:
            reason = f"no temporary folder could be made for git to run in ({err.strerror or type(err).__name__})"
    if reason:
        h["skipped_reason"] = reason
        if since:
            h["since_error"] = f"history was not read ({reason}); this is a full scan"
        return
    with home as home_dir:
        env = git_env(s.root, home_dir)
        read_history(s, lambda *args: run_git(exe, s.root, env, args, deadline), since)


def read_history(s, git, since):
    h = s.history
    count = git("rev-list", "--count", "HEAD")
    h["git"] = count is not None or git("rev-parse", "--git-dir") is not None
    h["commits"] = int(count.strip()) if count and count.strip().isdigit() else None
    # Newest first; tags made at the same moment, highest version first. The last --sort is the main key.
    tags = git("for-each-ref", "--count=20", "--sort=-version:refname", "--sort=-creatordate",
               "--format=%(refname:lstrip=2)", "refs/tags")
    h["tags"] = [t for t in (tags or "").splitlines() if t][:20]
    last = git("log", "-1", "--format=%H", "--", root_readme(s.files) or "README.md")
    h["last_readme_commit"] = (last or "").strip() or None
    if not since:
        return
    resolved = None if since.startswith("-") else git("rev-parse", "--verify", "--quiet", since + "^{commit}")
    if not resolved or not resolved.strip():
        h["since_error"] = f"{since} does not name a commit here; this is a full scan"
        return
    commit = resolved.strip()
    # Commit to commit only: comparing with the working tree would run the repository's clean filters.
    diff = git("diff", "--name-status", "-M", "-z", "--no-ext-diff", "--no-textconv", commit, "HEAD")
    others = git("ls-files", "--others", "--exclude-standard", "-z")
    if diff is None or others is None:
        h["since_error"] = "git could not list the changes; this is a full scan"
        return
    h["since"] = since
    fields = diff.split("\0")
    i = 0
    while i < len(fields) - 1:
        status = fields[i][:1]
        if status in "RC" and i + 2 < len(fields):
            h["changed"].append({"path": fields[i + 2], "status": "R" if status == "R" else "A", "from": fields[i + 1]})
            i += 3
        else:
            h["changed"].append({"path": fields[i + 1], "status": status if status in "AMD" else "M"})
            i += 2
    h["untracked"] = [p for p in others.split("\0") if p]
    s.focus = {c["path"] for c in h["changed"] if c["status"] != "D"} | set(h["untracked"])


# ---------------------------------------------------------------- assembly


def finish_kinds(s):
    cli_entries = [e for e in s.entry_points if e["_cli"]]
    options = [c for c in s.surfaces["cli"] if c["kind"] in ("subcommand", "option")]
    mcp_only = ("extension", "mcp-server") in s.kinds and not options
    if cli_entries and not mcp_only:
        for e in cli_entries[:3]:
            s.kind("terminal", "cli", "high", e["path"], e["line"], f"{e['via']} installs the command {e['name']}")
    elif s.entry_points and not mcp_only and len(options) >= 3:
        s.kind("terminal", "cli", "medium", options[0]["path"], options[0]["line"], "the program parses command-line options")
    if ("terminal", "tui") in s.kinds and ("terminal", "cli") not in s.kinds:
        del s.kinds[("terminal", "tui")]
    if not s.entry_points:
        # Option parsers in modules nothing installs are helpers, not the project's CLI.
        s.surfaces["cli"] = []
    s.surfaces["api"].sort(key=lambda a: a["kind"] == "type")
    focus_surfaces(s)


def focus_surfaces(s):
    """With --since, keep only the surfaces from changed files (and manifests); the kinds used them all."""
    for category, items in s.surfaces.items():
        if isinstance(items, list) and any(i.get("_unfocused") for i in items):
            s.surfaces[category] = [i for i in items if not i.get("_unfocused")]


# What a dynamic registration leaves unknown.
DYNAMIC_AREAS = {"tool registration": "tools", "tool": "tools", "registerTool": "tools", "addTool": "tools",
                 "NewTool": "tools", "route": "routes", "add_argument": "cli", "add_parser": "cli", "Shortcut": "shortcuts"}


def gaps(report):
    """What a discovery report could not establish, as [{"area", "path", "why"}].

    area is "sources" (code that was not read), "manifests", or a surface category whose
    names were registered dynamically. A name missing from an area with a gap may still
    exist, so a comparison must not call it absent.
    """
    out = []
    if report["truncated"]:
        why = "the scan stopped at %d files" % report["limits"]["max_files"]
        out += [{"area": "sources", "path": None, "why": why}, {"area": "manifests", "path": None, "why": why}]
    skipped = report["skipped"]
    sample = skipped["sample"]
    for e in sample:
        path, reason = e["path"], e["reason"]
        if reason == "too-large" and not (Scanner.is_test(path) or Scanner.is_example(path)):
            name = path.rsplit("/", 1)[-1]
            if name in MANIFEST_NAMES or posixpath.splitext(name)[1] in MANIFEST_SUFFIXES:
                out.append({"area": "manifests", "path": path, "why": "too large to read"})
            elif posixpath.splitext(name)[1].lower() in LANGS:
                out.append({"area": "sources", "path": path, "why": "too large to read"})
        elif reason == "unreadable" and not (Scanner.is_test(path) or Scanner.is_example(path)):
            name = path.rsplit("/", 1)[-1]
            if name in MANIFEST_NAMES or posixpath.splitext(name)[1] in MANIFEST_SUFFIXES:
                out.append({"area": "manifests", "path": path, "why": "could not be read"})
            elif posixpath.splitext(name)[1].lower() in LANGS:
                out.append({"area": "sources", "path": path, "why": "could not be read"})
        elif reason == "malformed":
            out.append({"area": "manifests", "path": path, "why": e.get("what") or "malformed"})
        elif reason == "capped":
            out.append({"area": e.get("area") or "sources", "path": path,
                        "why": "more than %d registrations, the rest not read" % CALL_LIMIT})
        elif reason == "dynamic":
            out.append({"area": DYNAMIC_AREAS.get(e.get("what"), "sources"), "path": path,
                        "why": "%s with a computed name" % (e.get("what") or "a registration")})
    # Past the sample, the counts still say that something went unread.
    counts = skipped.get("reasons") or Counter(e["reason"] for e in sample)
    shown = Counter(e["reason"] for e in sample)
    for reason, areas in (("too-large", ("sources", "manifests")), ("unreadable", ("sources", "manifests")),
                          ("malformed", ("manifests",)), ("dynamic", ("tools", "routes", "cli", "shortcuts")),
                          ("capped", ("tools", "routes", "cli", "shortcuts"))):
        if counts.get(reason, 0) > shown[reason]:
            why = "%d more files %s" % (counts[reason] - shown[reason], reason.replace("-", " "))
            out += [{"area": area, "path": None, "why": why} for area in areas]
    return out


def public_manifest(m):
    """A manifest as reported: script names without their commands, URLs without user names or passwords."""
    out = dict(m, scripts=list(m.get("scripts") or []))
    for key in ("homepage", "repository"):
        out[key] = safety.strip_userinfo(out.get(key))
    return out


def report(s):
    docs, pictures, examples, tests, rules = scan_docs(s)
    langs = Counter(lang for lang in s.langs.values() if lang)
    if "C" in langs and "C++" in langs:
        headers = sum(1 for f, lang in s.langs.items() if lang == "C" and f.endswith(".h"))
        langs["C++"] += headers
        langs["C"] -= headers
    order = {"dynamic": 0, "capped": 0, "unreadable": 0, "malformed": 0, "symlink": 1, "secret": 2, "too-large": 3,
             "binary": 4, "cap": 5, "installed-skill": 6, "dir": 6}
    kinds = sorted(s.kinds.items(), key=lambda kv: (-CONFIDENCE[kv[1]["confidence"]], KIND_ORDER.index(kv[0][0])))
    return {
        "tool": "discover", "version": VERSION, "root": ".", "truncated": s.truncated,
        "limits": {"max_files": s.max_files, "max_bytes": s.max_bytes},
        "files": len(s.files),
        "skipped": {"count": s.skip_count, "reasons": dict(sorted(s.skip_reasons.items())),
                    "sample": sorted(s.skipped, key=lambda e: order.get(e["reason"], 9))[:SAMPLE_LIMIT]},
        "languages": {k: v for k, v in sorted(langs.items(), key=lambda kv: (-kv[1], kv[0])) if v > 0},
        "manifests": [public_manifest(m) for m in s.manifests],
        "kinds": [{"kind": k, "subkind": sub, "confidence": v["confidence"], "evidence": v["evidence"]} for (k, sub), v in kinds],
        "entry_points": [{k: v for k, v in e.items() if not k.startswith("_")} for e in s.entry_points],
        "surfaces": s.surfaces, "channels": s.channels, "platforms": s.platforms, "signals": s.signals,
        "docs": docs, "pictures": pictures, "examples": examples, "tests": tests, "project_rules": rules,
        "history": s.history,
    }


ECOSYSTEMS = (scan_manifests, scan_sources, python_ecosystem, node_ecosystem, rust_ecosystem, go_ecosystem,
              desktop_ecosystem, agent_ecosystem, automation_ecosystem, service_ecosystem, finish_kinds)


def scan(root, *, max_files=5000, max_bytes=262144, since=None):
    """Scan the project at root (a folder, or a safety.Tree pinned by the caller) and return the report as a dict.

    Raises OSError (NotADirectoryError, PermissionError, ...) if root cannot be read.
    """
    s = Scanner(root, max_files, max_bytes)
    try:
        s.walk()
        git_history(s, since)
        for step in ECOSYSTEMS:
            step(s)
        return report(s)
    finally:
        s.close()


def to_text(r):
    out = [f"discover {r['version']}: {r['files']} files" + (f", stopped at {r['limits']['max_files']} (truncated)" if r["truncated"] else "")]
    if r["languages"]:
        out.append("Languages: " + ", ".join(f"{k} {v}" for k, v in list(r["languages"].items())[:6]))
    out.append("Kinds:" if r["kinds"] else "Kinds: none found")
    for k in r["kinds"]:
        ev = k["evidence"][0]
        out.append(f"  {k['kind']}/{k['subkind'] or '-'} ({k['confidence']}): {ev['path']}:{ev['line']} {ev['why']}")
    if r["entry_points"]:
        out.append("Entry points: " + ", ".join(f"{e['name']} ({e['via']}, {e['path']}:{e['line']})" for e in r["entry_points"]))
    if r["channels"]:
        out.append("Channels: " + ", ".join(c["channel"] + (f" {c['name']}" if c["name"] else "") for c in r["channels"]))
    counts = [f"{k} {len(v)}" for k, v in r["surfaces"].items() if isinstance(v, list) and v]
    if r["surfaces"]["action"]:
        a = r["surfaces"]["action"]
        counts.append(f"action ({len(a['inputs'])} inputs, {len(a['outputs'])} outputs, runs {a['runs']})")
    out.append("Surfaces: " + (", ".join(counts) or "none"))
    d = r["docs"]
    present = [d[k] for k in ("readme", "guide", "changelog", "contributing") if d[k]]
    if d["license"]["path"]:
        present.append(f"{d['license']['path']} ({d['license']['spdx'] or 'unknown'})")
    out.append("Docs: " + (", ".join(present) or "none"))
    out.append(f"Pictures: {len(r['pictures']['images'])} images" + (", scripts: " + ", ".join(r["pictures"]["scripts"]) if r["pictures"]["scripts"] else ""))
    reasons = Counter(e["reason"] for e in r["skipped"]["sample"])
    out.append(f"Skipped: {r['skipped']['count']}" + (" (" + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())) + " in sample)" if reasons else ""))
    h = r["history"]
    if h["git"]:
        out.append(f"History: {h['commits']} commits" + (", tags " + ", ".join(h["tags"][:5]) if h["tags"] else ""))
        if h["since"]:
            out.append(f"Since {h['since']}: {len(h['changed'])} changed, {len(h['untracked'])} untracked")
    if h["since_error"]:
        out.append("Since: " + h["since_error"])
    return "\n".join(out)


def main(argv=None):
    parser = safety.ArgumentParser(prog="discover.py", description="Scan a project, read-only, and report what it is and what it offers.")
    parser.add_argument("--root", default=".", help="project folder to scan (default: .)")
    parser.add_argument("--since", metavar="REF", help="also list committed changes since REF, plus untracked files; "
                        "uncommitted edits to tracked files are not listed. Surfaces come from those files and the manifests")
    parser.add_argument("--max-files", type=int, default=5000, metavar="N", help="stop after N files (default: 5000)")
    parser.add_argument("--max-bytes", type=int, default=262144, metavar="N", help="skip files larger than N bytes (default: 262144)")
    parser.add_argument("--format", choices=("json", "text"), default=None, help="output format (default: text on a terminal, json otherwise)")
    args = parser.parse_args(argv)
    if args.max_files < 1 or args.max_bytes < 1:
        parser.error("--max-files and --max-bytes take a number of 1 or more")
    try:
        result = scan(args.root, max_files=args.max_files, max_bytes=args.max_bytes, since=args.since)
    except OSError as err:
        print(safety.sanitize(f"discover.py: cannot read {args.root}: {err.strerror or err}", newlines=False),
              file=sys.stderr)
        return 2
    except Exception as err:  # a bug, or input no parser expected: report it without a traceback
        print(safety.sanitize(f"discover.py: the scan failed ({type(err).__name__}: {err})", newlines=False),
              file=sys.stderr)
        return 2
    fmt = args.format or ("text" if sys.stdout.isatty() else "json")
    # Secret-shaped values are replaced and control characters escaped in every format.
    if fmt == "text":
        print(to_text(safety.sanitize(result, newlines=False)))
    else:
        print(json.dumps(safety.sanitize(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
