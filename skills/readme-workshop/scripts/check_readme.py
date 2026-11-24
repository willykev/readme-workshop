#!/usr/bin/env python3
"""Check a README against the project it describes.

    check_readme.py [--root DIR] [--readme PATH] [--stdin] [--kind K[,K]]
                    [--format text|json|github] [--strict] [--config FILE | --no-config]

Errors are established defects (a broken link, a placeholder left in, an
input the Action does not have). Warnings are editorial. Manual findings are
what a file cannot settle. Exit 0 when there are no errors (and no warnings
with --strict), 1 otherwise, 2 on bad usage or unreadable input.

The checker reads only inside the root (and a config file the caller names
by its full path), never follows a link out of it, never opens a secrets
file, never writes, and never imports or runs project code. Standard library
only.
"""

from __future__ import annotations

import bisect
import difflib
import heapq
import json
import os
import posixpath
import re
import sys
import urllib.parse

# The sibling modules come from this folder and nowhere else, and no bytecode is
# written beside them: the skill may be installed inside the project it checks.
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if sys.path[:1] != [HERE]:
    sys.path.insert(0, HERE)
import formats  # noqa: E402
import mdfacts  # noqa: E402
import safety  # noqa: E402
from safety import PRIVATE_KEY_RE, SECRETS, redact  # noqa: E402,F401  (redact is part of this module's interface)

TOOL, VERSION = "check_readme", "0.1.2"

# Prose words a README of each kind reads best with (RW101). With several
# kinds, the widest range applies.
# Rough guides: each kind's target plus a few hundred words of room, so only a page well
# outside what its kind needs gets a warning.
WORD_RANGES = {
    "app": (300, 1200),
    "terminal": (250, 1200),
    "service": (300, 1300),
    "library": (150, 1400),
    "extension": (200, 1600),
    "automation": (200, 1600),
}

# Adjectives that claim a quality and need a number beside them (RW104).
FILLER_WORDS = ("fast", "blazing", "simple", "easy", "powerful", "modern", "beautiful", "seamless",
                "next-generation", "lightweight", "intuitive", "robust", "cutting-edge")

SEVERITY = {
    "RW001": "error", "RW002": "error", "RW003": "error", "RW004": "error", "RW005": "error",
    "RW006": "error", "RW007": "error", "RW008": "error", "RW009": "error", "RW010": "warning",
    "RW011": "error", "RW012": "error", "RW013": "error", "RW014": "error",
    **{"RW%d" % n: "warning" for n in range(101, 115)},
    **{"RW%d" % n: "manual" for n in range(201, 205)},
}

MB = 1024 * 1024
MAX_README, MAX_OTHER = 8 * MB, 2 * MB
LINKED_BUDGET = 32 * MB  # bytes of linked Markdown and example files read, in all
MAX_FINDINGS = 500  # findings listed; past this, one RW114 says how many more there were
MAX_NAMES = 10  # names a finding lists from a manifest or the code
CONFIG_NAME = ".readme-workshop.json"
# Findings a project's own config cannot silence: a leaked secret, a target outside the
# project, and an analysis that could not finish.
UNIGNORABLE = {"RW013", "RW014", "RW114"}
MD_EXTS = (".md", ".markdown", ".mdown", ".mkd")
SHELL_INFOS = {"sh", "bash", "shell", "console", "zsh", "fish", "shell-session", "shellsession", "terminal", "ksh"}
SESSION_INFOS = {"console", "shell-session", "shellsession", "terminal"}
GENERIC_ALT = {"image", "img", "screenshot", "screen shot", "screenshots", "demo", "gif", "picture",
               "photo", "preview", "alt", "alt text"}
GITHUB_ROUTES = {"issues", "pulls", "pull", "wiki", "releases", "actions", "discussions", "security",
                 "tags", "compare", "projects", "pulse", "graphs", "network", "stargazers", "watchers",
                 "forks", "fork", "blob", "tree", "raw", "commits", "commit", "branches", "milestones",
                 "labels", "settings", "packages", "contributors", "community", "archive", "subscription"}
KNOWN_TOOLS = set("""
    git cd ls cp mv rm mkdir cat echo export source sudo doas curl wget tar unzip make cmake meson ninja
    gcc cc clang go cargo rustup npm npx pnpm yarn bun bunx deno node python python3 py pip pip3 pipx uv
    uvx poetry conda brew apt apt-get dnf yum pacman yay paru zypper apk snap flatpak nix docker podman
    kubectl helm gh glab code claude codex gemini agy grok java mvn gradle dotnet ruby gem bundle rake php
    composer swift xcodebuild flutter dart mix erl ssh scp chmod chown ln touch set env eval exec time sh
    bash zsh fish pwsh powershell systemctl journalctl open xdg-open winget scoop choco qmake qmake6 tsc
    vite next jest pytest tox nox ruff black mypy aws gcloud az terraform""".split())
NUM_UNIT_RE = re.compile(r"(?<!\d)\d+(?:[.,]\d+)?\s*(?:%|×|x\b|ms\b|µs|us\b|ns\b|s\b|secs?\b|seconds?\b|"
                         r"minutes?\b|min\b|hours?\b|[kKMGT]i?B\b|bytes?\b|fps\b|frames?\b|Hz\b|req|"
                         r"requests?\b|ops\b|qps\b|rps\b|times\b|k\b|M\b)")
SPEED_RE = re.compile(r"\b(?:\d+(?:\.\d+)?\s*)?[x×] faster\b|\bfaster than\b|\bblazing\w*|"
                      r"\binstant(?:ly|aneous(?:ly)?)?\b", re.I)
INSTALL_CMD_RE = re.compile(r"\binstall\b|\buses:\s|\bnpm i\b|\b(?:yarn|pnpm|cargo|poetry|uv) add\b|"
                            r"\bgo get\b|\bdocker (?:run|pull)\b|\bgit clone\b")
EMOJI_CODE_RE = re.compile(r"(?:^|\s):[a-z0-9_+-]{2,}:(?=\s|$)")
STRUCTURE_RE = re.compile(r"^\s*(?:</?(?:div|p|center|span|br|hr|picture|source|details|summary)\b[^>]*>\s*)+$",
                          re.I)
IDIOM_RE = re.compile(r".*\bfail(?:s|ed|ing)? fast\b|.*\b(?:easy|simple) to (?:get wrong|miss|forget|break|"
                      r"overlook|lose|confuse|misuse|mistake|misread)")
USES_RE = re.compile(r"^(\s*)(-\s+)?uses:\s*['\"]?([^\s'\"#]+)")

# Template leftovers (RW002). Underscore-joined tokens are read from the
# skill's own templates at run time; this list is the fallback.
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
TEMPLATE_FILES = ("README.template.md", "guide.template.md")
FALLBACK_TOKENS = ("PLATFORM_OR_HOST", "WHAT_YOU_DO_WITH_IT", "ONE_SENTENCE_THAT_SETS_IT_APART",
                   "WHAT_THE_PICTURE_SHOWS", "WHAT_YOU_CAN_DO_AND_HOW", "INSTALL_COMMAND", "NEXT_STEP",
                   "UPDATE_COMMAND", "REMOVE_COMMAND", "WHAT_IS_LEFT_BEHIND", "FIRST_THING_PEOPLE_DO",
                   "RUN_OR_PRESS_THIS", "WHAT_HAPPENS", "SENTENCE_WITH_THE_COMMAND_OR_KEY", "REAL_OUTPUT",
                   "WHAT_THE_GUIDE_HOLDS", "LICENSE_NAME")
SINGLE_TOKENS = {"NAME", "CATEGORY", "LABEL", "TASK", "REQUIREMENTS", "SYMPTOM", "WHY", "FIX"}
TEMPLATE_PHRASES = re.compile(r"\bNAME is an?\b|\bis an? CATEGORY\b|\*\*(?:LABEL|SYMPTOM)\.\*\*|"
                              r"\bNAME needs\b|\bneeds REQUIREMENTS\b|\bWHY\. FIX\b|\b(?:build|change) NAME\b")
TEMPLATE_COMMENTS = ("Copy this file", "A README skeleton for any kind of project", "docs/guide.md: the manual")
TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
PLACEHOLDER_RES = ((re.compile(r"\bTODO\b|\bTBD\b"), "a TODO or TBD note"),
                   (re.compile(r"lorem ipsum", re.I), "lorem ipsum"),
                   (re.compile(r"\bAppName\b|\bappname\b"), "the template's AppName"))
OWNER_RE = re.compile(r"(?:github\.com[/:]|gitlab\.com[/:]|uses:\s*)OWNER/")
# A bracket slot is literal [text] left from a template: one of its words,
# lowercase words with spaces ("what you do with it"), or a whole sentence.
SLOT_RE = re.compile(r"(?<![\]!\\\[])\[([^\[\]\n]{1,120})\](?![\[(:]|\s*\()")
SLOT_WORDS = {"category", "platform", "desktop", "desktop and version", "format", "machine", "version", "n",
              "task", "your things", "os and versions", "license", "name", "description", "project name",
              "app name", "tagline", "feature", "screenshot", "link", "url", "username", "repo", "owner"}
SLOT_SHAPE_RE = re.compile(r"^(?:[a-z][a-z,/'’ -]*(?: [a-z,/'’-]+){2,}|[A-Z][^.!?]*(?: \S+){3,}[.:])$")

class UsageError(Exception):
    """Bad arguments or input the checker cannot read (exit 2)."""


class Root:
    """File access confined to one folder: nothing outside it is opened.

    Reads go through safety.Tree, which pins the folder for the whole check
    and refuses secrets files, as named and as resolved.
    """

    def __init__(self, path):
        try:
            self.tree = safety.Tree(path)
        except (OSError, ValueError):
            raise UsageError("the root is not a folder: %s" % path) from None
        self.abs = self.tree.abs

    def close(self):
        self.tree.close()

    def inside(self, real):
        return self.tree.inside(real)

    def is_secret(self, rel, real):
        """True if a path, as written or as resolved, is a secrets file or lies in a secrets folder."""
        return safety.is_secret_path(rel) or safety.is_secret_path(os.path.relpath(real, self.abs))

    def locate(self, base, target):
        """Resolve a path written in the README; return (status, rel, real).

        status is ok, missing, outside, or github (a page such as ../../issues
        that GitHub serves beside the repository). Nothing outside the root
        is touched beyond resolving the symlinks that lead there.
        """
        p = target.replace("\\", "/")
        absolute = p.startswith("/")
        if re.match(r"^[A-Za-z]:/|^~", p):
            return "outside", p, None
        rel = posixpath.normpath(p.lstrip("/") if absolute else posixpath.join(base, p))
        if rel == ".." or rel.startswith("../"):
            parts = rel.split("/")
            if not absolute and len(parts) > 2 and parts[:2] == ["..", ".."] and parts[2] in GITHUB_ROUTES:
                return "github", rel, None
            return "outside", p, None
        broken = ("outside" if absolute else "missing"), (p if absolute else rel).replace("\0", "%00"), None
        if "\0" in rel:  # %00 in a link: no file has that name, and the file system refuses to look
            return broken
        try:
            real = os.path.realpath(os.path.join(self.abs, *[s for s in rel.split("/") if s not in ("", ".")]))
            if not self.inside(real):
                return "outside", p, None
            return ("ok", rel, real) if os.path.exists(real) else broken
        except (OSError, ValueError):
            return broken

    def read_bytes(self, path, limit):
        """Up to limit bytes of a regular file inside the root (a path relative to it, or absolute), or None.

        safety.Tree.read_bytes refuses secrets files and opens the file from the
        root down without following symlinks, so a file or folder swapped after
        its path was checked is not read.
        """
        try:
            rel = os.path.relpath(path, self.abs) if os.path.isabs(path) else path
        except ValueError:  # another drive on Windows
            return None
        return self.tree.read_bytes(rel, limit)

    def read(self, path, limit=MAX_OTHER):
        """Text of a regular file inside the root, or None if it is too large, unreadable or refused."""
        return safety.decode_text(self.read_bytes(path, limit + 1), limit)


class Context:
    """Everything the rules share: the page, its facts, the project, the findings."""

    def __init__(self, root, readme, text, cfg):
        self.root, self.readme, self.text, self.cfg = root, readme, text, cfg
        self.base = posixpath.dirname(readme)
        self.facts = mdfacts.facts(text, path=readme)
        self.head_lines = [h["line"] for h in self.facts["headings"]]
        self.lines = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").split("\n")
        if self.lines[-1] == "":
            self.lines.pop()
        self.ignore = set(cfg["ignore"]) - UNIGNORABLE
        self.findings, self.counted, self._scan, self._files = [], 0, False, {}
        self.totals = {"error": 0, "warning": 0, "manual": 0}
        self.kinds = []
        self.linked_bytes, self.linked_skipped = 0, False

    def add(self, rid, line, message, fix=""):
        """Record a finding, unless the config ignores it; only the first MAX_FINDINGS in page order are kept."""
        if rid in self.ignore:
            return
        self.counted += 1
        self.totals[SEVERITY[rid]] += 1
        self.findings.append({"id": rid, "severity": SEVERITY[rid], "path": self.readme, "line": line,
                              "message": message, "fix": fix})
        if len(self.findings) >= 2 * MAX_FINDINGS:
            self.findings = heapq.nsmallest(MAX_FINDINGS, self.findings, key=finding_order)

    def listed(self):
        """The findings to report, in page order, with one RW114 when there were more than MAX_FINDINGS."""
        findings = heapq.nsmallest(MAX_FINDINGS, self.findings, key=finding_order)
        more = self.counted - len(findings)
        if more > 0:
            findings.append({"id": "RW114", "severity": SEVERITY["RW114"], "path": self.readme, "line": None,
                             "message": "The page has %d more findings than the %d listed." % (more, MAX_FINDINGS),
                             "fix": "Fix the ones listed, then run the check again."})
            self.totals["warning"] += 1
        return findings

    def scan(self):
        """Project discovery, run once; None if it failed (reported as RW114, so --strict fails)."""
        if self._scan is False:
            try:
                import discover
                self._scan = discover.scan(self.root.tree, max_files=2000)
            except Exception as exc:  # discovery is best effort; the page checks still run
                self._scan = None
                self.add("RW114", None, "Project discovery failed (%s), so the README's names were not "
                         "compared with the code." % type(exc).__name__,
                         "Run discover.py on the root to see why, then compare names by hand.")
        return self._scan

    def gaps(self, *areas):
        """What discovery could not read in these areas ("sources", "manifests", or a surface
        category); a name missing there may still exist. Empty when it read them all."""
        scan = self.scan()
        if not scan:
            return []
        import discover
        return [g for g in discover.gaps(scan) if g["area"] in areas]

    def incomplete(self, line, names, gaps):
        """RW114: names the page gives that discovery did not find, where it could not read everything."""
        where = sorted({g["path"] + " (" + g["why"] + ")" if g["path"] else g["why"] for g in gaps})
        self.add("RW114", line, "Discovery could not read all of the project (%s), so %s could not be confirmed." %
                 ("; ".join(where[:3]) + ("; and more" if len(where) > 3 else ""), some(names)),
                 "Check by hand that each one exists in the code.")

    def section(self, line):
        """Text of the nearest heading above a line, lowercased."""
        heads = self.facts["headings"]
        k = bisect.bisect_left(self.head_lines, line)
        return heads[k - 1]["text"].lower() if k else ""

    def project_file(self, rel, real):
        """(text, why) of a file the page links to or quotes; why is None, "large", "unreadable" or "budget".

        Each file is read once, however many links name it. The bytes read count
        against LINKED_BUDGET; past it, nothing more is read.
        """
        if real not in self._files:
            if self.linked_bytes >= LINKED_BUDGET:
                self.linked_skipped = True
                return None, "budget"
            data = self.root.read_bytes(rel, MAX_OTHER + 1)
            self.linked_bytes += len(data or b"")
            text = safety.decode_text(data, MAX_OTHER)
            why = None if text is not None else "unreadable" if data is None else "large"
            self._files[real] = {"text": text, "why": why}
        entry = self._files[real]
        return entry["text"], entry["why"]

    def other_facts(self, rel, real):
        """(facts, why) of another Markdown file; facts is None when it was not read (see project_file)."""
        text, why = self.project_file(rel, real)
        if text is None:
            return None, why
        entry = self._files[real]
        if "facts" not in entry:
            entry["facts"] = mdfacts.facts(text, path=rel)
        return entry["facts"], None

    def manifests(self):
        return (self.scan() or {}).get("manifests") or []

    def is_kind(self, kind, subkind):
        return any(k.get("kind") == kind and k.get("subkind") == subkind for k in (self.scan() or {}).get("kinds") or [])

    def surfaces(self):
        return (self.scan() or {}).get("surfaces") or {}


def finding_order(f):
    return f["line"] or 0, f["id"]


def some(names, limit=MAX_NAMES):
    """Names joined by commas, at most limit of them, then how many more there are."""
    names = list(names)
    shown = ", ".join(map(str, names[:limit]))
    return shown + (" and %d more" % (len(names) - limit) if len(names) > limit else "")


# ----------------------------------------------------------------- the page

def rule_placeholders(c):
    """RW002: template text left in the page."""
    f, tokens = c.facts, template_tokens()
    heads = {h["line"]: h["text"] for h in f["headings"]}
    manpage = bool({"SYNOPSIS", "DESCRIPTION"} & set(heads.values()))
    alts = {}
    for img in f["images"]:
        alts.setdefault(img["line"], []).append(img["alt"])
    for idx, kind in enumerate(f["line_kinds"]):
        found, raw, prose = [], c.lines[idx], f["prose"][idx]
        if kind != "comment" and OWNER_RE.search(raw):
            found.append("OWNER/")
        if kind in ("fence", "code"):  # the template's own code blocks, such as INSTALL_COMMAND
            found += [t for t in TOKEN_RE.findall(raw) if t in tokens]
        if kind in ("text", "heading", "table", "html"):
            found += [label for rx, label in PLACEHOLDER_RES  # a heading named TODO is a roadmap, not a slot
                      if rx.search(prose) and not (kind == "heading" and label.startswith("a TODO"))]
            found += [m.group(0) for m in SLOT_RE.finditer(prose) if m.group(1).strip().lower() in SLOT_WORDS
                      or SLOT_SHAPE_RE.match(m.group(1).strip())]
            found += [t for t in TOKEN_RE.findall(prose) if t in tokens]
            found += [m.group(0) for m in TEMPLATE_PHRASES.finditer(prose)]
            words = heads.get(idx + 1, "").split()
            if kind == "heading":  # "# NAME", "# NAME guide", "## TASK"; not a man page's NAME
                if words and words[0] in ("NAME", "TASK") and len(words) <= 2 and not manpage:
                    found.append(words[0])
            elif re.sub(r"^[\s>*_-]*|[\s*_.:]*$", "", prose) in SINGLE_TOKENS:
                found.append(prose.strip(" >*_-.:"))
        found += [t for alt in alts.get(idx + 1, ()) for t in TOKEN_RE.findall(alt) if t in tokens]
        if found:
            c.add("RW002", idx + 1, "Template text is still in the page: %s." % ", ".join(dict.fromkeys(found)),
                  "Replace it with the project's own words, or delete the line.")
    for com in f["comments"]:
        if any(p in com["text"] for p in TEMPLATE_COMMENTS):
            c.add("RW002", com["line"], "The template's instructions comment is still in the page.",
                  "Delete the template's comments once the page is filled in.")


def template_tokens():
    found = set()
    for name in TEMPLATE_FILES:
        try:
            with open(os.path.join(ASSETS, name), encoding="utf-8") as fh:
                found.update(TOKEN_RE.findall(re.sub(r"<!--.*?-->", "", fh.read(), flags=re.S)))
        except OSError:
            continue
    return found or set(FALLBACK_TOKENS)


def rule_fences(c):
    """RW003 unclosed fences, RW107 prompts in copyable blocks, RW202 commands to run."""
    shell = []
    for fence in c.facts["fences"]:
        if fence["end_line"] is None:
            c.add("RW003", fence["line"], "This code block is never closed, so the rest of the page renders "
                  "as code.", "Close it with a line of %s." % ("```" if "`" in c.lines[fence["line"] - 1] else "~~~"))
        info = fence_info(fence)
        body = [l for l in fence["text"].split("\n") if l.strip() and not l.lstrip().startswith("#")]
        if info == "" and body and re.match(r"\s*\$ ", body[0]):
            shell.append(fence)
            c.add("RW107", fence["line"], "The commands in this block start with a prompt, which breaks "
                  "copying them.", "Drop the leading $, and mark the block sh.")
            continue
        if info not in SHELL_INFOS:
            continue
        shell.append(fence)
        prompted = [l for l in body if re.match(r"\s*[$>] ", l)]
        if not prompted:
            continue
        if info in SESSION_INFOS:
            if len(prompted) == len(body):
                c.add("RW107", fence["line"], "This %s block shows prompts but no output." % info,
                      "Mark it sh and drop the prompts, so the commands can be copied as they are.")
        elif re.match(r"\s*[$>] ", body[0]):
            c.add("RW107", fence["line"], "The commands in this %s block start with a prompt, which breaks "
                  "copying them." % info, "Drop the leading $ or >, or mark the block console and show output.")
    if shell:
        c.add("RW202", shell[0]["line"], "The page shows commands.",
              "Run each one as written, in a scratch folder, and confirm it does what the page says.")


def fence_info(fence):
    return (fence["info"].split() or [""])[0].lower().strip("{}.")


FILE_URL = object()  # split_target's answer for a file: URL, which leads off the project


def split_target(target):
    """FILE_URL for file: URLs, None for other URLs, else (path, fragment, query)."""
    t = target.strip()
    t = t[1:-1] if t.startswith("<") and t.endswith(">") else t
    if not t or t.startswith("//"):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", t) and not re.match(r"^[A-Za-z]:[\\/]", t):
        return FILE_URL if t.lower().startswith("file:") else None
    path, _, frag = t.partition("#")
    path, _, query = path.partition("?")
    return urllib.parse.unquote(path), urllib.parse.unquote(frag), query


def has_anchor(facts, frag):
    frag = frag.strip()
    if frag.lower().startswith("user-content-"):
        frag = frag[len("user-content-"):]
    if not frag or frag.lower() == "top":
        return True
    if "_anchors" not in facts:  # built once per page, however many links point at it
        anchors = {h["anchor"] for h in facts["headings"]} | set(facts["ids"])
        facts["_anchors"] = anchors | {a.lower() for a in anchors}
    return frag in facts["_anchors"] or frag.lower() in facts["_anchors"]


def rule_links(c):
    """RW004 missing files, RW005 missing anchors, RW014 targets outside the root, RW204 anchors not checked."""
    seen, unchecked = set(), {}
    for link in c.facts["links"]:
        parts = split_target(link["target"])
        key = (link["line"], link["target"])
        # An autolink is an address, except a file: URL, which still leads off the project.
        if not parts or key in seen or (link["kind"] == "autolink" and parts is not FILE_URL):
            continue
        seen.add(key)
        if parts is FILE_URL:
            outside(c, link["line"], "link", link["target"])
            continue
        path, frag, query = parts
        if path and not path.startswith(("/", "\\")) and \
                posixpath.normpath(posixpath.join(c.base, path.replace("\\", "/"))) == c.readme:
            path = ""  # a link to this page by its name: its anchors are this text's, not a copy on disk
        if not path:
            if frag and not has_anchor(c.facts, frag):
                c.add("RW005", link["line"], "The link to #%s points to a heading this page does not have." % frag,
                      "Link to an existing heading's anchor (lowercase, punctuation dropped, spaces as "
                      "hyphens), or add the heading.")
            continue
        status, rel, real = c.root.locate(c.base, path)
        if status == "outside":
            outside(c, link["line"], "link", path)
        elif status == "missing":
            c.add("RW004", link["line"], "The link to %s points to a file that does not exist." % rel,
                  "Correct the path (it is read from %s) or add the file." % (c.base or "the root"))
        elif status == "ok" and frag and "plain=1" not in query and rel.lower().endswith(MD_EXTS) \
                and os.path.isfile(real):
            if c.root.is_secret(rel, real):
                c.add("RW204", link["line"], "%s looks like a secrets file, so it was not read to check the "
                      "anchor #%s." % (rel, frag), "Check the anchor by hand, and link to a document instead.")
                continue
            other, why = c.other_facts(rel, real)
            if other is not None and not has_anchor(other, frag):
                c.add("RW005", link["line"], "%s has no heading for the anchor #%s." % (rel, frag),
                      "Link to one of its headings' anchors, or add the heading there.")
            elif other is None and why != "budget":
                unchecked.setdefault(rel, (link["line"], why, []))[2].append("#" + frag)
    for rel, (line, why, frags) in unchecked.items():
        c.add("RW204", line, "%s is %s, so the link%s to %s %s not checked." %
              (rel, "larger than %d MB" % (MAX_OTHER // MB) if why == "large" else "unreadable",
               "s" if len(frags) > 1 else "", some(dict.fromkeys(frags)), "were" if len(frags) > 1 else "was"),
              "Check that each anchor names one of its headings, by hand.")


def outside(c, line, what, target):
    target = target.replace("\0", "%00")
    note = (" GitHub reads a path that starts with / from the repository root, where nothing exists "
            "at that path." if target.startswith("/") else "")
    c.add("RW014", line, "The %s target %s leads outside the project, so it was not read.%s" % (what, target, note),
          "Point it at a file inside the repository, or use a full https:// address.")


def rule_images(c):
    """RW006 missing images, RW014, RW106 heavy files, RW110 alt text, RW201 pictures."""
    pictures = [i for i in c.facts["images"] if not mdfacts.BADGE_RE.search(i["src"])]
    for img in c.facts["images"]:
        parts = split_target(img["src"])
        if parts is FILE_URL:
            outside(c, img["line"], "image", img["src"])
        elif parts and parts[0]:
            status, rel, real = c.root.locate(c.base, parts[0])
            if status == "outside":
                outside(c, img["line"], "image", parts[0])
            elif status == "missing" or (status == "ok" and not os.path.isfile(real)):
                c.add("RW006", img["line"], "The image %s does not exist." % rel,
                      "Correct the path (it is read from %s) or add the picture." % (c.base or "the root"))
            elif status == "ok":
                try:
                    size, ext = os.path.getsize(real), posixpath.splitext(rel)[1].lower()
                except OSError:
                    continue
                if size > 3 * MB or (ext in (".png", ".jpg", ".jpeg") and size > MB):
                    c.add("RW106", img["line"], "%s weighs %.1f MB, slow to load on the page." % (rel, size / MB),
                          "Shrink it (fewer colors, smaller frame, or a short loop) to under %s." %
                          ("1 MB" if ext in (".png", ".jpg", ".jpeg") else "3 MB"))
    for img in pictures:
        alt = re.sub(r"[^\w\s.-]", "", img["alt"].lower()).strip()
        stem = posixpath.splitext(posixpath.basename(img["src"].split("?")[0]))[0].lower()
        if not alt or alt in GENERIC_ALT or re.fullmatch(r"[\w.-]+\.(png|jpe?g|gif|svg|webp|avif|bmp)", alt) \
                or alt == stem:
            c.add("RW110", img["line"], "The picture's alt text (%s) does not say what it shows." %
                  ("empty" if not alt else img["alt"]),
                  "Describe what the picture shows, in a sentence a screen reader can read out.")
    if pictures:
        c.add("RW201", pictures[0]["line"], "The page has %d picture%s." % (len(pictures), "s"[len(pictures) == 1:]),
              "Check that each one reads at 600 and at 900 px wide.")


def rule_markers(c):
    """RW007 and RW008: example blocks marked to match a file."""
    for mk in c.facts["markers"]:
        fence = c.facts["fences"][mk["fence"]]
        status, rel, real = c.root.locate(c.base, mk["path"])
        if status == "outside":
            outside(c, mk["line"], "example marker", mk["path"])
            continue
        if status != "ok" or not os.path.isfile(real):
            c.add("RW008", mk["line"], "The example marker names %s, which %s." %
                  (rel, "does not exist" if status == "missing" else "is not a file"),
                  "Correct the path (it is read from %s) or add the file." % (c.base or "the root"))
            continue
        if c.root.is_secret(rel, real):
            c.add("RW204", mk["line"], "The example marker names %s, which looks like a secrets file, so it was "
                  "not read." % rel, "Compare the block with a made-up sample instead, by hand.")
            continue
        content, why = c.project_file(rel, real)
        if why == "budget":
            continue  # reported once, as RW114
        if content is None:
            c.add("RW204", mk["line"], "%s is too large or unreadable to compare with its example." % rel,
                  "Compare the block with the file by hand.")
            continue
        lines = content.split("\n")
        lines = lines[:-1] if lines and lines[-1] == "" else lines
        if mk["start"] is not None:
            if mk["start"] < 1 or mk["end"] < mk["start"] or mk["end"] > len(lines):
                c.add("RW008", mk["line"], "The example marker asks for lines %d-%d of %s, which has %d lines."
                      % (mk["start"], mk["end"], rel, len(lines)), "Correct the line range.")
                continue
            lines = lines[mk["start"] - 1: mk["end"]]
        if fence["end_line"] is None:
            continue
        want, got = trimmed(lines), trimmed(fence["text"].split("\n"))
        if want != got:
            k = next((k for k, (a, b) in enumerate(zip(want, got)) if a != b), min(len(want), len(got)))
            c.add("RW007", fence["line"], "The example differs from %s, first at its line %d." %
                  (rel, k + 1 + (mk["start"] or 1) - 1), "Copy the block again from the file, or update the file.")


def trimmed(lines):
    out = [l.rstrip() for l in lines]
    while out and not out[-1]:
        out.pop()
    return out


def rule_secrets(c):
    """RW013: secret-shaped values anywhere in the file, comments and code included."""
    for idx, line in enumerate(c.lines):
        for label, rx, keep, real in SECRETS:
            for m in rx.finditer(line):
                if real(m.group(0)):
                    c.add("RW013", idx + 1, "The page holds what looks like a real %s (%s****)." %
                          (label, m.group(0)[:keep]), "Remove it, revoke it, and show a placeholder instead.")
        if PRIVATE_KEY_RE.search(line) and idx + 1 < len(c.lines) \
                and re.fullmatch(r"[A-Za-z0-9+/=]{40,}", c.lines[idx + 1].strip()):
            c.add("RW013", idx + 1, "The page holds what looks like a private key.",
                  "Remove it, replace the key, and show a placeholder instead.")


def rule_shape(c):
    """RW101 length, RW102 install, RW103 badges, RW105 emoji, RW109 contents, RW111, RW113."""
    f, kinds = c.facts, c.kinds
    lo, hi = c.cfg.get("words") or word_range(kinds)
    if not lo <= f["words"] <= hi:
        c.add("RW101", None, "The page has %d prose words; %s README reads best with %d to %d." %
              (f["words"], ("an " if kinds[:1] and kinds[0][0] in "aeiou" else "a ") + " or ".join(kinds) if kinds
               else "a", lo, hi),
              "Cut what the guide can hold." if f["words"] > hi else "Add what an installer needs to know.")
    install = f["install_line"]
    early = any(fe["line"] <= 50 and INSTALL_CMD_RE.search(fe["text"]) for fe in f["fences"])
    if not (kinds and set(kinds) == {"automation"}) and (install is None or install > 50) and not early:
        c.add("RW102", install, "The install steps start at line %d." % install if install else
              "The page has no install section.", "Put an Install section within the first 50 lines.")
    badges = [b for b in f["badges"] if b["line"] <= 15]
    if len(badges) > 2:
        c.add("RW103", badges[0]["line"], "%d badges in the first 15 lines push the pitch down." % len(badges),
              "Keep two at most at the top, or move them to the end.")
    for h in f["headings"]:
        if EMOJI_CODE_RE.search(h["text"]) or any(is_emoji(ch) for ch in h["text"]):
            c.add("RW105", h["line"], "The heading %r has an emoji." % h["text"],
                  "Drop it: it adds noise to the anchor and to screen readers.")
    if f["toc"] and f["lines"] < 250:
        line = next((l["line"] for l in f["links"] if l["target"].startswith("#")), None)
        c.add("RW109", line, "A table of contents on a page of %d lines." % f["lines"],
              "Drop it: GitHub shows an outline of the headings already.")
    rule_first_screen(c)
    heads = f["headings"]
    for k, h in enumerate(heads):
        nxt = heads[k + 1] if k + 1 < len(heads) else None
        stop = nxt["line"] - 1 if nxt else len(f["line_kinds"])
        body = [kd for kd in f["line_kinds"][h["line"]:stop] if kd not in ("blank", "comment", "heading")]
        if not body and (nxt is None or nxt["level"] <= h["level"]):
            c.add("RW113", h["line"], "The heading %r has nothing under it." % h["text"],
                  "Fill the section or delete the heading.")


def word_range(kinds):
    ranges = [WORD_RANGES[k] for k in kinds if k in WORD_RANGES] or list(WORD_RANGES.values())
    return min(r[0] for r in ranges), max(r[1] for r in ranges)


def is_emoji(ch):
    o = ord(ch)
    return (0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF or 0x23E9 <= o <= 0x23FA
            or o in (0x231A, 0x231B, 0x2B05, 0x2B06, 0x2B07, 0x2B1B, 0x2B1C, 0x2B50, 0x2B55))


def rule_first_screen(c):
    """RW111: lines of badges, logos and notices before the first sentence."""
    f = c.facts
    kinds, prose = f["line_kinds"], f["prose"]
    first = next((k for k, kd in enumerate(kinds) if kd in ("text", "html")
                  and len(mdfacts.WORD_RE.findall(prose[k])) >= 5), None)
    if first is None:
        return
    start = 0
    heads = [h for h in f["headings"] if h["line"] - 1 < first]
    if heads:
        start = heads[0]["line"]
        while start < first and kinds[start] == "heading":
            start += 1
    busy = [k for k in range(start, first) if kinds[k] not in ("blank", "comment", "hr", "raw")
            and not STRUCTURE_RE.match(c.lines[k])]
    if len(busy) > 3:
        c.add("RW111", busy[0] + 1, "%d lines of badges, logos or notices come before the first sentence." % len(busy),
              "Start with the sentence that says what the project is; move the rest below it or to the end.")


def sentences(c):
    """(line, sentence) pairs: list items, headings and table rows stand alone."""
    f, units, cur, cur_kind = c.facts, [], [], None
    for idx, kind in enumerate(f["line_kinds"]):
        item = bool(mdfacts.LIST_RE.match(c.lines[idx].lstrip(" >")))
        if kind == "text" and cur and cur_kind == "text" and not item:
            cur.append((idx + 1, f["prose"][idx]))
            continue
        if cur:
            units.append(cur)
        cur, cur_kind = ([(idx + 1, f["prose"][idx])] if kind in ("text", "heading", "table", "html") else []), kind
    if cur:
        units.append(cur)
    for unit in units:
        parts = [t.strip() + " " for _, t in unit]
        offsets = [0]
        for part in parts[:-1]:
            offsets.append(offsets[-1] + len(part))
        for m in re.finditer(r"(?:[^.!?]|[.!?](?!\s))+[.!?]*", "".join(parts)):
            body = m.group(0)
            if body.strip():
                at = m.start() + len(body) - len(body.lstrip())
                yield unit[bisect.bisect_right(offsets, at) - 1][0], body.strip()


def rule_wording(c):
    """RW104 filler adjectives with no number, RW108 speed claims with no measurement."""
    singles = {w for w in FILLER_WORDS if "-" not in w}
    for line, sent in sentences(c):
        speed = [m.group(0) for m in SPEED_RE.finditer(sent)]
        if speed and not NUM_UNIT_RE.search(sent):
            c.add("RW108", line, "%s, with no measurement beside it." % ", ".join('"%s"' % s for s in speed),
                  "Give the number and unit (for example 40 ms or 2 MB) and how it was measured, or cut it.")
        if NUM_UNIT_RE.search(sent):
            continue
        found = []
        for k, m in enumerate(mdfacts.WORD_RE.finditer(sent)):
            word = m.group(0)
            low, parts = word.lower(), word.lower().split("-")
            hit = low in FILLER_WORDS or (len(parts) > 1 and parts[-1] in singles) or \
                (len(parts) > 2 and parts[1] == "to" and parts[0] in singles)
            if IDIOM_RE.match(sent[max(0, m.start() - 8): m.end() + 22].lower().lstrip()):
                hit = False
            if hit and not (k and word[0].isupper()) and not (speed and "blazing" in low):
                found.append(word)
        if found:
            c.add("RW104", line, "%s, with nothing measurable beside it." % ", ".join('"%s"' % w for w in found),
                  "Replace it with a number or a concrete fact the reader can check, or cut it.")


# --------------------------------------------------------------- the project

def rule_action(c):
    """RW009 Action inputs and outputs against action.yml; RW112 snippets pinned to a branch.

    A snippet's `uses: owner/repo/folder@ref` runs this project's Action when owner and repo are
    this repository's (the folder's own name stands in when no remote or manifest names an owner);
    the folder picks the action.yml it is compared with.
    """
    root_action = c.surfaces().get("action")
    actions, ident = {}, None

    def action_in(folder):
        if folder not in actions:
            action = actions[folder] = read_action(c, folder, root_action)
            if action and not action.get("certain"):
                c.add("RW204", None, "%s could not be read for certain, so the README's inputs and outputs were "
                      "not compared with it." % action["path"], "Compare them by hand.")
        return actions[folder]

    primary = action_in("") if root_action else None
    for fence in c.facts["fences"]:
        lines = fence["text"].split("\n")
        for k, line in enumerate(lines):
            m = USES_RE.match(line)
            if not m:
                continue
            ident = ident or own_repo(c)
            folder = own_action_folder(m.group(3), ident)
            action = action_in(folder) if folder is not None else None
            if action is None:
                continue
            ref = m.group(3).rpartition("@")[2]
            if ref in ("main", "master"):
                c.add("RW112", fence["line"] + 1 + k, "The snippet runs this Action from @%s, which changes "
                      "under its users." % ref, "Pin a release tag (or a full commit SHA) instead.")
            if not action["certain"]:
                continue
            inputs = {name.lower() for name in action["inputs"]}
            for key, at in step_inputs(lines, k):
                if key.lower() not in inputs:
                    c.add("RW009", fence["line"] + 1 + at, "The snippet passes %s, which %s does not declare as an "
                          "input." % (key, action["path"]), "Use one of: %s." % (some(sorted(inputs)) or "none"))
    used = [a for a in actions.values() if a]
    primary = primary or (used[0] if len(used) == 1 else None)
    if not primary or not primary["certain"]:
        return
    inputs = {k.lower() for k in primary["inputs"]}
    outputs = {k.lower() for k in primary["outputs"]}
    for table in c.facts["tables"]:
        which = io_table(c, table)
        if not which:
            continue
        declared = inputs if which == "input" else outputs
        for row in table["rows"]:
            name = mdfacts.plain(row["cells"][0]).strip("`* ") if row["cells"] else ""
            if re.fullmatch(r"[A-Za-z_][\w-]*", name) and name.lower() not in declared:
                c.add("RW009", row["line"], "The %ss table lists %s, which %s does not declare." %
                      (which, name, primary["path"]), "Remove the row, or declare the %s there." % which)
    for name, spec in primary["inputs"].items():
        spec = spec or {}
        if spec.get("required") is True and spec.get("default") is None and \
                not re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(name), c.text, re.I):
            c.add("RW009", None, "The required input %s is never mentioned." % name,
                  "Show it in the usage snippet and the inputs table.")


def read_action(c, folder, root_action):
    """The Action declared in a folder of the project: discovery's for the root, else read here."""
    if root_action and posixpath.dirname(root_action.get("path") or "") == folder:
        return root_action
    for name in ("action.yml", "action.yaml"):
        status, rel, real = c.root.locate("", posixpath.join(folder, name) if folder else name)
        if status == "ok" and c.root.tree.refusal(rel) == "secret":
            c.add("RW204", None, "%s lies in or leads to a secrets folder, so it was not read." % rel,
                  "Compare the snippet's inputs with it by hand.")
            return None
        text = c.root.read(rel) if status == "ok" and os.path.isfile(real) else None
        if text is not None:
            import discover
            return discover.action_surface(rel, text)
    return None


def own_repo(c):
    """(pairs, names): the (owner, repo) pairs this checkout is published as, where its remotes or
    manifests say, and every repository name it goes by, the folder's own name included."""
    pairs, names = set(), {os.path.basename(c.root.abs).lower()}
    urls = [str(m.get(k) or "") for m in c.manifests() for k in ("repository", "homepage")]
    # Only the remotes' github.com owner and name are taken from git's config; nothing of it is printed.
    config = c.root.tree.read_text(".git/config", MAX_OTHER, follow=False, git_data=True)
    urls += re.findall(r"url\s*=\s*(\S+)", config or "")
    for url in urls:
        m = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", url)
        if m:
            pairs.add((m.group(1).lower(), m.group(2).lower()))
            names.add(m.group(2).lower())
    return pairs, names


def own_action_folder(uses, ident):
    """The folder of this project's Action that a `uses:` value runs ("" for the root), or None."""
    if uses.startswith("./"):
        folder = uses[2:].split("@")[0].strip("/")
        return posixpath.normpath(folder) if folder else ""
    m = re.match(r"([\w.-]+)/([\w.-]+)(/[^@]*)?@(.+)$", uses)
    if not m:
        return None
    pairs, names = ident
    owner, repo = m.group(1).lower(), m.group(2).lower()
    if ((owner, repo) not in pairs) if pairs else (repo not in names):
        return None
    return (m.group(3) or "").strip("/")


def step_inputs(lines, k):
    """(key, line index) for each input under `with:` in the step whose `uses:` is lines[k],
    in block or flow form, before or after the `uses:` line."""
    m = USES_RE.match(lines[k])
    col = len(m.group(1)) + len(m.group(2) or "")  # the column the step's keys start at
    first = k
    if not m.group(2):  # walk up to the line that opens the step: its dash, or its first key
        for j in range(k - 1, -1, -1):
            line = lines[j]
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            dash = re.match(r"\s*-\s+", line)
            opens = dash is not None and dash.end() == col
            if not opens and len(line) - len(line.lstrip(" ")) < col:
                break
            first = j
            if opens:
                break
    end = k + 1
    while end < len(lines) and (not lines[end].strip() or lines[end].lstrip().startswith("#")
                                or len(lines[end]) - len(lines[end].lstrip(" ")) >= col):
        end += 1
    # Cut at the keys' column: the dash goes with it, and the step reads as one mapping. A comment
    # line, at any indent, is left out.
    data, _ = formats.read_yaml("\n".join("" if lines[j].lstrip().startswith("#") else lines[j][col:]
                                           for j in range(first, end)))
    inputs = data.get("with") if isinstance(data, dict) else None
    if not isinstance(inputs, dict):
        return []
    with_at = next((j for j in range(first, end) if re.match(r"\s*(?:-\s+)?with\s*:", lines[j])), k)
    found = []
    for key in map(str, inputs):
        key_re = re.compile(r"(?:^\s*|[{,]\s*)['\"]?%s['\"]?\s*:" % re.escape(key))
        found.append((key, next((j for j in range(with_at, end) if key_re.search(lines[j])), with_at)))
    return found


def io_table(c, table):
    """'input', 'output' or None for a table that lists an Action's inputs or outputs."""
    first = mdfacts.plain(table["header"][0]).strip("`* ").lower() if table["header"] else ""
    heading = c.section(table["line"])
    if first in ("input", "inputs"):
        return "input"
    if first in ("output", "outputs"):
        return "output"
    if first in ("name", "parameter", "key", "option", "argument"):
        has_in, has_out = bool(re.search(r"\binputs?\b", heading)), bool(re.search(r"\boutputs?\b", heading))
        return "input" if has_in and not has_out else "output" if has_out and not has_in else None
    return None


def rule_bins(c):
    """RW010: the first command of an install or usage block names no declared binary."""
    bins = {b for m in c.manifests() for b in (m.get("bins") or []) if isinstance(b, str)}
    if not bins:
        return
    names = {n.lower().split("/")[-1] for n in bins | {m.get("name") or "" for m in c.manifests()}
             | {os.path.basename(c.root.abs)} if n}
    for fence in c.facts["fences"]:
        if fence_info(fence) not in SHELL_INFOS | {""} or not re.search(
                r"install|usage|use\b|using|quick ?start|get(ting)? started|example|command|cli|run",
                c.section(fence["line"])):
            continue
        body = [l.strip() for l in fence["text"].split("\n") if l.strip() and not l.strip().startswith("#")]
        if not body:
            continue
        words = [w for w in re.sub(r"^[$>]\s+", "", body[0]).split()
                 if not re.match(r"^\w+=", w) and w not in ("sudo", "doas", "time", "exec", "command")]
        if not words or "/" in words[0] or words[0] in KNOWN_TOOLS or words[0] in bins:
            continue
        word = words[0].lower()
        if not any(looks_like(word, n) for n in names):
            continue
        gaps = c.gaps("manifests")
        if gaps:  # an unread manifest may declare it
            c.incomplete(fence["line"] + 1, [words[0]], gaps)
        else:
            c.add("RW010", fence["line"] + 1, "The block runs %s, but the manifests declare %s." %
                  (words[0], some(sorted(bins))), "Use the command the package installs, or declare it.")


def looks_like(word, name):
    """A name close enough to another to be a typo or an old name for it."""
    if word == name:
        return True
    if "-" in word and "-" in name and word.split("-")[0] == name.split("-")[0] and len(word.split("-")[0]) >= 3:
        return True
    return len(word) >= 4 and difflib.SequenceMatcher(None, word, name).ratio() >= 0.85


def rule_tools(c):
    """RW011: MCP tool names in the README's tool table that the code does not register.

    With no name read from the code, an MCP server's table cannot be confirmed
    (RW114); any other project's is left alone.
    """
    tools = {t.get("name") for t in c.surfaces().get("tools") or [] if t.get("name")}
    if not tools and not c.is_kind("extension", "mcp-server"):
        return
    gaps = c.gaps("sources", "tools")  # unread code, or tools registered under computed names
    if not tools and not gaps:
        gaps = [{"area": "tools", "path": None, "why": "no tool registration could be read"}]
    for table in c.facts["tables"]:
        first = mdfacts.plain(table["header"][0]).strip("`* ").lower() if table["header"] else ""
        if not (first in ("tool", "tools", "tool name") or (first == "name" and "tool" in c.section(table["line"]))):
            continue
        unconfirmed = []
        for row in table["rows"]:
            name = mdfacts.plain(row["cells"][0]).strip("`* ") if row["cells"] else ""
            if not re.fullmatch(r"[A-Za-z][\w.-]*", name) or name in tools:
                continue
            if gaps:
                unconfirmed.append(name)
            else:
                c.add("RW011", row["line"], "The tool %s is not registered in the code." % name,
                      "Use the registered name (%s), or remove the row." % some(sorted(tools)))
        if unconfirmed:
            c.incomplete(table["line"], unconfirmed, gaps)


def rule_names(c):
    """RW012: plugin and skill names in this project's install commands against plugin.json and SKILL.md.

    A command counts as this project's when it names this repository, this
    marketplace, or a name close to one of its own: a README may also install
    other plugins as prerequisites.
    """
    plugins, skills, markets, unsure = set(), set(), set(), []
    for m in c.manifests():
        kind, name = m.get("type"), m.get("name")
        if kind in ("plugin.json", "SKILL.md"):
            (plugins if kind == "plugin.json" else skills).add(name) if name else unsure.append(m.get("path") or kind)
        elif kind == "marketplace.json":
            path = m.get("path") or kind
            data = formats.parse_json(c.root.read(path) or "")
            data = data if isinstance(data, dict) else {}
            listed = data.get("plugins") if data.get("plugins") is not None else []
            if not isinstance(data.get("name"), str) or not isinstance(listed, list):
                c.add("RW204", None, "%s has no marketplace name or plugin list that could be read, so install "
                      "commands were not checked against it." % path, "Check the names in them by hand.")
            if isinstance(data.get("name"), str):
                markets.add(data["name"])
            plugins.update(p["name"] for p in (listed if isinstance(listed, list) else [])
                           if isinstance(p, dict) and isinstance(p.get("name"), str))
    skills.update(s.get("name") for s in c.surfaces().get("skills") or [] if s.get("name"))
    repos = own_repo(c)[1]
    for idx, line in enumerate(c.lines):
        if c.facts["line_kinds"][idx] == "comment":
            continue
        checks = [(m.group(1), plugins, "plugin.json")
                  for m in re.finditer(r"(?:^|[\s`/])plugin install\s+([\w.-]+)(?:@([\w.-]+))?", line)
                  if m.group(2) in markets or any(looks_like(m.group(1).lower(), p.lower()) for p in plugins)]
        checks += [(m.group(2), skills, "SKILL.md")
                   for m in re.finditer(r"\bgh skills? (?:install|add)\s+[\w.-]+/([\w.-]+)\s+([\w.-]+)", line)
                   if m.group(1).lower() in repos]
        checks += [(m.group(2), skills, "SKILL.md")
                   for m in re.finditer(r"\bskills add\s+[\w.-]+/([\w.-]+)\b.*?--skill[= ]([\w.-]+)", line)
                   if m.group(1).lower() in repos]
        for name, known, source in checks:
            gaps = c.gaps("manifests") if known and name not in known else []
            if gaps:  # an unread manifest may hold the name
                c.incomplete(idx + 1, [name], gaps)
            elif known and name not in known:
                c.add("RW012", idx + 1, "The install command names %s, but %s says %s." %
                      (name, source, some(sorted(known))), "Use the name from %s." % source)
            elif not known and unsure:
                c.add("RW204", idx + 1, "%s has no name that could be read, so %s was not checked." %
                      (unsure[0], name), "Check the name by hand.")


# ---------------------------------------------------------------- running

RULES = (rule_placeholders, rule_fences, rule_links, rule_images, rule_markers, rule_secrets,
         rule_shape, rule_wording, rule_action, rule_bins, rule_tools, rule_names)


def parse_kinds(value):
    if value is None:
        return None
    items = value if isinstance(value, (list, tuple)) else str(value).split(",")
    kinds = [str(k).strip().lower() for k in items if str(k).strip()]
    bad = [k for k in kinds if k not in WORD_RANGES]
    if bad or not kinds:
        raise UsageError("unknown kind %s; use %s" % (", ".join(bad) or "(none)", ", ".join(WORD_RANGES)))
    return kinds


def load_config(root, config):
    """The settings to apply.

    config is None (ROOT/.readme-workshop.json if it exists), a file path
    (relative to the root and inside it, or absolute and anywhere), or a dict.
    """
    if config is None:
        if not os.path.isfile(os.path.join(root.abs, CONFIG_NAME)):
            return {"kind": None, "ignore": [], "words": None}
        config = CONFIG_NAME
    if isinstance(config, (str, os.PathLike)):
        data = formats.parse_json(read_config(root, os.fspath(config)))
        if not isinstance(data, dict):
            raise UsageError("the config %s is not a JSON object" % config)
        config = data
    cfg = {"kind": parse_kinds(config.get("kind")), "ignore": config.get("ignore") or [], "words": config.get("words")}
    if not isinstance(cfg["ignore"], list) or not all(isinstance(i, str) for i in cfg["ignore"]):
        raise UsageError("config ignore must be a list of rule IDs")
    words = cfg["words"]
    if words is not None and not (isinstance(words, list) and len(words) == 2 and
                                  all(isinstance(w, int) for w in words) and 0 <= words[0] <= words[1]):
        raise UsageError("config words must be [min, max]")
    return cfg


def read_config(root, path):
    """Text of a config file: one the caller names in full may be anywhere; a relative one is read from the root.

    Neither may be, or lead to, a secrets file.
    """
    if os.path.isabs(path):
        real = os.path.realpath(path)
        if safety.is_secret_path(path) or safety.is_secret_path(real):
            raise UsageError("the config %s is or leads to a secrets file, which is never read" % path)
        text = safety.read_text(real, MAX_OTHER)
    else:
        why = root.tree.refusal(path)
        if why == "outside":
            raise UsageError("the config %s leads outside the root" % path)
        if why == "secret":
            raise UsageError("the config %s is or leads to a secrets file, which is never read" % path)
        text = root.read(path)
    if text is None:
        raise UsageError("cannot read the config %s: it must be a regular file of at most %d MB" %
                         (path, MAX_OTHER // MB))
    return text


def check(root, readme_path="README.md", text=None, kinds=None, config=None):
    """Check one README; return the result dict described in the module doc."""
    root_obj = Root(root)
    try:
        return run_checks(root, root_obj, readme_path, text, kinds, config)
    finally:
        root_obj.close()


def run_checks(root, root_obj, readme_path, text, kinds, config):
    cfg = load_config(root_obj, config)
    kinds = parse_kinds(kinds) or cfg["kind"]
    rel = str(readme_path).replace("\\", "/")
    if os.path.isabs(rel):
        rel = os.path.relpath(os.path.realpath(rel), root_obj.abs).replace(os.sep, "/")
    rel = posixpath.normpath(rel)
    if rel == ".." or rel.startswith("../") or rel == ".":
        raise UsageError("the README path %s is not inside the root" % readme_path)
    stdin = text is not None
    if text is None:
        why = root_obj.tree.refusal(rel)
        if why == "outside":
            raise UsageError("%s leads outside the root" % rel)
        if why == "secret":
            raise UsageError("%s is or leads to a secrets file, which is never read" % rel)
        if os.path.isfile(root_obj.tree.resolve(rel)):
            text = root_obj.read(rel, MAX_README)
            if text is None:
                raise UsageError("cannot read %s (unreadable, or larger than 8 MB)" % rel)
    blank = text is None or not re.search(r"\S", text)  # before anything parses it
    c = Context(root_obj, rel, "" if blank else text, cfg)
    c.kinds = kinds or []
    if blank:
        c.add("RW001", None, "%s %s." % (rel, "does not exist" if text is None else "is empty"),
              "Write the README: what it is, how to install it, and a first result.")
    else:
        if kinds is None:
            kinds = sorted({k["kind"] for k in (c.scan() or {}).get("kinds") or []
                            if k.get("confidence") in ("high", "medium") and k.get("kind") in WORD_RANGES})
        c.kinds = kinds
        for rule in RULES:
            rule(c)
        if c.linked_skipped:
            c.add("RW114", None, "The files the page links to or quotes add up to more than %d MB, so some anchors "
                  "and examples were not checked." % (LINKED_BUDGET // MB), "Check the rest by hand.")
        if "extension" in kinds:
            c.add("RW203", None, "This is an extension.",
                  "Install it in each host the README names and confirm it loads there.")
    findings = c.listed()
    f = c.facts
    result = {
        "tool": TOOL, "version": VERSION,
        "target": {"root": str(root), "readme": rel, "stdin": stdin},
        "kinds": c.kinds,
        "facts": {"words": f["words"], "lines": f["lines"] if text else 0,
                  "pictures": len([i for i in f["images"] if not mdfacts.BADGE_RE.search(i["src"])]),
                  "badges": len(f["badges"]), "install_line": f["install_line"], "code_blocks": len(f["fences"])},
        "findings": findings,
        "totals": c.totals,
    }
    return safety.sanitize(result)


def format_text(result):
    result = safety.sanitize(result, newlines=False)  # each value stays on its own line
    out = []
    for f in result["findings"]:
        loc = f["path"] + (":%d" % f["line"] if f["line"] else "")
        out.append("%s: %s %s %s" % (loc, f["severity"], f["id"], f["message"]))
        if f["fix"]:
            out.append("    Fix: " + f["fix"])
    t = result["totals"]
    out.append("%s, %s, %s (%s; %d words)." % (plural(t["error"], "error"), plural(t["warning"], "warning"),
               plural(t["manual"], "manual check"), ", ".join(result["kinds"]) or "kind unknown",
               result["facts"]["words"]))
    return "\n".join(out)


def plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def gh_data(s):
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def gh_prop(s):
    return gh_data(s).replace(":", "%3A").replace(",", "%2C")


def format_github(result, root):
    try:
        prefix = os.path.relpath(os.path.realpath(root), os.getcwd()).replace(os.sep, "/")
    except ValueError:  # another drive on Windows
        prefix = ".."
    prefix = str(root).replace(os.sep, "/") if prefix.startswith("..") else prefix
    prefix, result = safety.sanitize(prefix), safety.sanitize(result)
    level = {"error": "error", "warning": "warning", "manual": "notice"}
    out = []
    for f in result["findings"]:
        props = ["file=" + gh_prop(posixpath.normpath(posixpath.join(prefix, f["path"])))]
        props += ["line=%d" % f["line"]] if f["line"] else []
        props.append("title=" + gh_prop(f["id"]))
        message = (f["message"] + " " + f["fix"]).strip()
        out.append("::%s %s::%s" % (level[f["severity"]], ",".join(props), gh_data(message)))
    t = result["totals"]
    out.append("%s, %s, %s." % (plural(t["error"], "error"), plural(t["warning"], "warning"),
                                plural(t["manual"], "manual check")))
    return "\n".join(out)


def main(argv=None):
    parser = safety.ArgumentParser(
        prog="check_readme.py", description="Check a README against the project it describes. Exit 0 when "
        "there are no errors (and no warnings with --strict), 1 otherwise, 2 on bad usage or unreadable input.")
    parser.add_argument("--root", default=".", help="project folder; nothing outside it is read, except a config "
                        "file you name by full path (default .)")
    parser.add_argument("--readme", default="README.md", help="README path relative to the root (default README.md)")
    parser.add_argument("--stdin", action="store_true", help="read the README text from stdin; --readme is its "
                        "logical path, so relative links resolve from its folder")
    parser.add_argument("--kind", help="project kinds, comma-separated: " + ", ".join(WORD_RANGES))
    parser.add_argument("--format", choices=("text", "json", "github"), default="text")
    parser.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--config", help="JSON config: a relative path is read from the root and must stay inside "
                        "it; a full path may be anywhere (default ROOT/%s if present). Its ignore list cannot "
                        "silence %s." % (CONFIG_NAME, ", ".join(sorted(UNIGNORABLE))))
    source.add_argument("--no-config", action="store_true", help="ignore ROOT/%s, as when checking a change "
                        "someone else proposed" % CONFIG_NAME)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        text = read_stdin() if args.stdin else None
        result = check(args.root, args.readme, text=text, kinds=args.kind, config={} if args.no_config else args.config)
    except UsageError as exc:
        print("check_readme: %s" % safety.sanitize(str(exc), newlines=False), file=sys.stderr)
        return 2
    except Exception as exc:  # a bug, or input no rule expected: report it without a traceback
        message = "the check failed (%s: %s)" % (type(exc).__name__, exc)
        print("check_readme: %s" % safety.sanitize(message, newlines=False), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.format == "github":
        print(format_github(result, args.root))
    else:
        print(format_text(result))
    t = result["totals"]
    return 1 if t["error"] or (args.strict and t["warning"]) else 0


def read_stdin():
    """The README text from stdin, up to MAX_README bytes."""
    data = sys.stdin.buffer.read(MAX_README + 1)
    if len(data) > MAX_README:
        raise UsageError("the README on stdin is larger than %d MB" % (MAX_README // MB))
    return data.decode("utf-8", "replace")


if __name__ == "__main__":
    sys.exit(main())
