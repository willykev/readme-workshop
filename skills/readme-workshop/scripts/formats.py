"""Readers for the file formats that project manifests use.

TOML goes through the standard library's tomllib, JSON through json, and
YAML through a small reader for the subset that action.yml, compose files,
.pre-commit-hooks.yaml and Markdown frontmatter use. Every reader returns
None (or a best partial value marked uncertain) instead of raising.

Standard library only; nothing here executes or imports project code.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tomllib

sys.dont_write_bytecode = True
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import safety  # noqa: E402

__all__ = [
    "read_toml",
    "read_json",
    "read_yaml",
    "frontmatter",
    "parse_toml",
    "parse_json",
]


# ---------------------------------------------------------------- TOML, JSON

MAX_FILE = 2 * 1024 * 1024  # read_toml and read_json refuse larger files


def parse_toml(text):
    """Parse TOML text; None on any error."""
    try:
        return tomllib.loads(text)
    except (tomllib.TOMLDecodeError, TypeError, ValueError, RecursionError):
        return None


def _read_file(path):
    """Bytes of a regular file of at most MAX_FILE bytes, or None (see safety.read_regular)."""
    data = safety.read_regular(path, MAX_FILE + 1)
    return data if data is not None and len(data) <= MAX_FILE else None


def read_toml(path):
    """Read a regular TOML file of at most MAX_FILE bytes; None if it cannot be read or parsed."""
    data = _read_file(path)
    try:
        return None if data is None else parse_toml(data.decode("utf-8"))
    except UnicodeDecodeError:
        return None


def parse_json(text):
    """Parse JSON text (a leading BOM is ignored); None unless it is an object or array."""
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None
    if text.startswith("﻿"):
        text = text[1:]
    try:
        value = json.loads(text)
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, (dict, list)) else None


def read_json(path):
    """Read a regular JSON file of at most MAX_FILE bytes, tolerant of a UTF-8 BOM; None on error."""
    data = _read_file(path)
    return None if data is None else parse_json(data)


# ---------------------------------------------------------------- YAML subset

_NULLS = {"", "~", "null", "Null", "NULL"}
_TRUES = {"true", "True", "TRUE"}
_FALSES = {"false", "False", "FALSE"}
_INT_RE = re.compile(r"[-+]?(0|[1-9][0-9_]*)$")
_HEX_RE = re.compile(r"0x[0-9a-fA-F_]+$")
_OCT_RE = re.compile(r"0o[0-7_]+$")
_FLOAT_RE = re.compile(r"[-+]?(\.[0-9]+|[0-9][0-9_]*(\.[0-9_]*)?)([eE][-+]?[0-9]+)?$")
_INF_NAN = {
    ".inf": float("inf"), ".Inf": float("inf"), ".INF": float("inf"),
    "+.inf": float("inf"), "+.Inf": float("inf"), "+.INF": float("inf"),
    "-.inf": float("-inf"), "-.Inf": float("-inf"), "-.INF": float("-inf"),
    ".nan": float("nan"), ".NaN": float("nan"), ".NAN": float("nan"),
}
_ESCAPES = {
    "0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n",
    "v": "\v", "f": "\f", "r": "\r", "e": "\x1b", " ": " ", '"': '"',
    "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0",
}
_BLOCK_HEADER_RE = re.compile(r"([|>])([-+]?)([1-9]?)([-+]?)\s*(#.*)?$")


def _resolve_plain(text):
    """Type a plain scalar the way the YAML 1.2 core schema does."""
    if text in _NULLS:
        return None
    if text in _TRUES:
        return True
    if text in _FALSES:
        return False
    if _INT_RE.match(text):
        try:
            return int(text.replace("_", ""))
        except ValueError:
            return text
    if _HEX_RE.match(text):
        return int(text[2:].replace("_", ""), 16)
    if _OCT_RE.match(text):
        return int(text[2:].replace("_", ""), 8)
    if text in _INF_NAN:
        return _INF_NAN[text]
    if _FLOAT_RE.match(text) and any(ch.isdigit() for ch in text):
        try:
            return float(text.replace("_", ""))
        except ValueError:
            return text
    return text


def _strip_comment(line, quote=None):
    """Drop a trailing # comment that sits outside quotes.

    quote is the quote character a quoted scalar from an earlier line left
    open; the line is read as starting inside it.
    """
    prev = " "
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if quote == '"' and ch == "\\":
                i += 2
                continue
            if ch == quote:
                if quote == "'" and line[i + 1:i + 2] == "'":
                    i += 2
                    continue
                quote = None
        elif ch in "'\"" and (prev.isspace() or prev in "[{,:-?"):
            quote = ch
        elif ch == "#" and prev.isspace():
            return line[:i].rstrip()
        prev = ch
        i += 1
    return line.rstrip()


def _find_key_colon(text):
    """Index of the ':' that ends a mapping key on this line, or -1."""
    if not text or text[0] in "[{|>":
        return -1
    i = 0
    if text[0] in "'\"":
        end = _quoted_end(text, 0)
        if end < 0:
            return -1
        i = end + 1
        while i < len(text) and text[i] in " \t":
            i += 1
        if text[i:i + 1] == ":" and (i + 1 == len(text) or text[i + 1] in " \t"):
            return i
        return -1
    while i < len(text):
        ch = text[i]
        if ch == "#" and i > 0 and text[i - 1].isspace():
            return -1
        if ch == ":" and (i + 1 == len(text) or text[i + 1] in " \t"):
            return i
        i += 1
    return -1


def _quoted_end(text, start):
    """Index of the closing quote for the quote at text[start], or -1."""
    quote = text[start]
    i = start + 1
    while i < len(text):
        ch = text[i]
        if quote == '"' and ch == "\\":
            i += 2
            continue
        if ch == quote:
            if quote == "'" and text[i + 1:i + 2] == "'":
                i += 2
                continue
            return i
        i += 1
    return -1


def _unquote(text):
    """Value of a complete quoted scalar (with its quotes)."""
    quote, body = text[0], text[1:-1]
    if quote == "'":
        return body.replace("''", "'")
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        nxt = body[i + 1:i + 2]
        if nxt in _ESCAPES:
            out.append(_ESCAPES[nxt])
            i += 2
        elif nxt in ("x", "u", "U"):
            width = {"x": 2, "u": 4, "U": 8}[nxt]
            digits = body[i + 2:i + 2 + width]
            try:
                out.append(chr(int(digits, 16)))
            except ValueError:
                out.append(digits)
            i += 2 + width
        else:
            out.append(nxt)
            i += 2
    return "".join(out)


class _YamlReader:
    def __init__(self, text):
        if text.startswith("﻿"):
            text = text[1:]
        self.lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        # The text's last line break ends its last line; it does not start an empty one.
        self.last_break = len(self.lines) > 1 and self.lines[-1] == ""
        if self.last_break:
            self.lines.pop()
        self.certain = True
        self.end = len(self.lines)

    def doubt(self):
        self.certain = False

    # Line helpers ----------------------------------------------------------

    def indent_of(self, line):
        stripped = line.lstrip(" ")
        if stripped.startswith("\t"):
            self.doubt()
        return len(line) - len(stripped)

    def significant(self, i):
        """Index of the next line that is not blank or a comment."""
        while i < self.end:
            stripped = self.lines[i].strip()
            if stripped and not stripped.startswith("#"):
                return i
            i += 1
        return i

    # Document --------------------------------------------------------------

    def parse(self):
        start = 0
        while start < self.end:
            stripped = self.lines[start].strip()
            if stripped.startswith("%"):
                start += 1
                continue
            if not stripped or stripped.startswith("#"):
                start += 1
                continue
            break
        if start < self.end and self.lines[start].rstrip() == "---":
            start += 1
        elif start < self.end and self.lines[start].startswith("--- "):
            rest = self.lines[start][4:]
            self.lines[start] = rest
        for j in range(start, self.end):
            line = self.lines[j]
            if line.rstrip() == "---" or line.startswith("--- "):
                tail = self.lines[j + 1:]
                if any(t.strip() and not t.strip().startswith("#") for t in tail):
                    self.doubt()
                self.end = j
                break
            if line.rstrip() == "...":
                if any(t.strip() and not t.strip().startswith("#") for t in self.lines[j + 1:]):
                    self.doubt()  # more after the end of the document: another document
                self.end = j
                break
        i = self.significant(start)
        if i >= self.end:
            return None
        value, i = self.node(i, -1)
        if self.significant(i) < self.end:
            self.doubt()
        return value

    def node(self, i, parent):
        """Parse the block node starting at line i, indented more than parent."""
        i = self.significant(i)
        if i >= self.end:
            return None, i
        line = self.lines[i]
        n = self.indent_of(line)
        if n <= parent:
            return None, i
        text = line[n:]
        if text == "-" or text.startswith("- ") or text.startswith("-\t"):
            return self.sequence(i, n)
        if text.startswith("? "):
            self.doubt()
            return self.mapping(i, n)
        if _find_key_colon(_strip_comment(text)) >= 0:
            return self.mapping(i, n)
        return self.inline(text, i, parent)

    def sequence(self, i, n):
        items = []
        while True:
            i = self.significant(i)
            if i >= self.end:
                break
            line = self.lines[i]
            if self.indent_of(line) != n:
                break
            text = line[n:]
            if not (text == "-" or text.startswith("- ") or text.startswith("-\t")):
                break
            rest = text[1:].lstrip(" \t")
            col = n + (len(text) - len(rest))
            content = _strip_comment(rest)
            if not content:
                value, i = self.node(i + 1, n)
            elif content.startswith(("- ", "? ")) or content == "-" or _find_key_colon(content) >= 0:
                # Reparse the rest of the line as a node at its own column.
                self.lines[i] = " " * col + rest
                value, i = self.node(i, n)
            else:
                value, i = self.inline(rest, i, n)
            items.append(value)
        return items, i

    def mapping(self, i, n):
        result = {}
        while True:
            i = self.significant(i)
            if i >= self.end:
                break
            line = self.lines[i]
            ind = self.indent_of(line)
            if ind != n:
                if ind > n:
                    self.doubt()
                    i += 1
                    continue
                break
            text = line[n:]
            if text.startswith("? ") or text == "?":
                self.doubt()
                i = self.skip_block(i + 1, n)
                continue
            if text == "-" or text.startswith("- "):
                break
            stripped = _strip_comment(text)
            colon = _find_key_colon(stripped)
            if colon < 0:
                self.doubt()
                i += 1
                continue
            key = self.key(stripped[:colon].rstrip())
            rest = text[colon + 1:].lstrip(" \t")
            if not _strip_comment(rest):
                nxt = self.significant(i + 1)
                if nxt < self.end:
                    nline = self.lines[nxt]
                    nind = self.indent_of(nline)
                    ntext = nline[nind:]
                    if nind == n and (ntext == "-" or ntext.startswith("- ")):
                        value, i = self.sequence(nxt, n)
                    else:
                        value, i = self.node(i + 1, n)
                else:
                    value, i = None, nxt
            else:
                value, i = self.inline(rest, i, n)
            if key == "<<":
                self.doubt()
                if isinstance(value, dict):
                    for k, v in value.items():
                        result.setdefault(k, v)
                continue
            try:
                result[key] = value
            except TypeError:
                self.doubt()
                result[str(key)] = value
        return result, i

    def key(self, text):
        text = self.props(text)
        if text[:1] in "'\"" and len(text) >= 2 and text[-1] == text[0]:
            return _unquote(text)
        if text[:1] in "[{":
            self.doubt()
            return text
        value = _resolve_plain(text)
        return value if isinstance(value, (str, int, bool)) or value is None else text

    def skip_block(self, i, n):
        while True:
            i = self.significant(i)
            if i >= self.end or self.indent_of(self.lines[i]) <= n:
                return i
            i += 1

    def props(self, text):
        """Strip anchors and tags from the front of a node, marking doubt."""
        while text[:1] in ("&", "!"):
            self.doubt()
            parts = text.split(None, 1)
            text = parts[1] if len(parts) > 1 else ""
        return text

    def inline(self, rest, i, parent):
        """Parse a value that starts on line i (after 'key:' or '- ')."""
        rest = self.props(rest.strip())
        content = _strip_comment(rest)
        if not content:
            return self.node(i + 1, parent)
        if content.startswith("*"):
            self.doubt()
            return None, i + 1
        header = _BLOCK_HEADER_RE.match(content)
        if header:
            return self.block_scalar(header, i, parent)
        if content[0] in "[{":
            return self.flow_value(content, i, parent)
        if content[0] in "'\"":
            return self.quoted(rest, i, parent)
        if _find_key_colon(content) >= 0:
            # 'key: a: b' is an error to a strict parser; keep the text.
            self.doubt()
        # Plain scalar, possibly continued on more-indented lines.
        parts = [content]
        j = i + 1
        while j < self.end:
            nline = self.lines[j]
            stripped = nline.strip()
            if not stripped:
                k = self.significant(j)
                if k < self.end and self.indent_of(self.lines[k]) > parent and not self.lines[k].strip().startswith("#"):
                    parts.append("\n" * (k - j))
                    j = k
                    continue
                break
            if stripped.startswith("#") or self.indent_of(nline) <= parent:
                break
            nxt = _strip_comment(stripped)
            if _find_key_colon(nxt) >= 0 or nxt.startswith("- "):
                self.doubt()
                break
            parts.append(nxt)
            j += 1
        text = ""
        for part in parts:
            if part.startswith("\n"):
                text += part
            elif text and not text.endswith("\n"):
                text += " " + part
            else:
                text += part
        if len(parts) == 1:
            return _resolve_plain(text), j
        return text, j

    def quoted(self, rest, i, parent):
        end = _quoted_end(rest, 0)
        if end >= 0:
            tail = _strip_comment(rest[end + 1:]).strip()
            if tail:
                self.doubt()
            return _unquote(rest[:end + 1]), i + 1
        # A quoted scalar that runs over several lines: fold the breaks. Only each
        # new line is searched for the closing quote, so the work stays linear.
        quote = rest[0]
        parts = [rest.rstrip()]
        j = i + 1
        while j < self.end:
            piece = self.lines[j].strip()
            j += 1
            last = parts[-1]
            if quote == '"' and (len(last) - len(last.rstrip("\\"))) % 2:  # an escaped line break
                parts[-1] = last[:-1]
            elif not piece:
                parts.append("\n")
                continue
            elif not last.endswith("\n"):
                parts.append(" ")
            close = _quoted_end(quote + piece, 0)
            if close < 0:
                parts.append(piece)
                continue
            text = "".join(parts) + piece[:close]
            if _strip_comment(piece[close:]).strip():
                self.doubt()
            return _unquote(text), j
        self.doubt()
        return "".join(parts)[1:], j

    def block_scalar(self, header, i, parent):
        style = header.group(1)
        chomp = header.group(2) or header.group(4)
        explicit = header.group(3)
        base = max(parent, 0)
        content_indent = base + int(explicit) if explicit else None
        if explicit and parent < 0:
            content_indent = int(explicit)
        raw = []
        j = i + 1
        while j < self.end:
            line = self.lines[j]
            if not line.strip():
                raw.append("")
                j += 1
                continue
            ind = len(line) - len(line.lstrip(" "))
            if content_indent is None:
                if ind <= parent:
                    break
                content_indent = ind
            if ind < content_indent:
                break
            raw.append(line[content_indent:])
            j += 1
        # Trailing blank lines belong to the scalar only for chomping. Every line read ends
        # in a line break, except the text's last line when the text has no final break.
        breaks = len(raw) - (j == len(self.lines) and not self.last_break)
        trailing = 0
        while raw and raw[-1] == "":
            raw.pop()
            trailing += 1
        if style == "|":
            body = "\n".join(raw)
        else:
            body = _fold(raw)
        if not raw:
            value = "\n" * breaks if chomp == "+" else ""
        else:
            after = breaks - len(raw) + 1  # line breaks after the last line with content
            value = body + ("" if chomp == "-" else "\n" * after if chomp == "+" else "\n" * min(after, 1))
        return value, j

    def flow_value(self, content, i, parent):
        """A flow collection, read on over as many lines as it takes to close, then parsed once."""
        parts, scan, j = [content], _FlowScan(), i + 1
        scan.feed(content)
        while not scan.closed and j < self.end:
            piece = _strip_comment(self.lines[j].strip(), scan.quote)  # a # in a quoted scalar is text
            parts.append(piece)
            scan.feed(" " + piece)
            j += 1
        parser = _FlowParser(" ".join(parts))
        try:
            value = parser.value()
        except _Incomplete:
            self.doubt()
            return parser.partial(), j
        except ValueError:
            self.doubt()
            return content, j
        parser.skip_space()
        if parser.pos != len(parser.text) or parser.doubt:
            self.doubt()
        return value, j


class _FlowScan:
    """Finds where a flow collection closes, a piece at a time, skipping brackets in quoted scalars.

    A quote opens a scalar only where _FlowParser starts a value: after [ { ,
    a ': ' or a map key's ':', or an anchor or tag.
    """

    def __init__(self):
        self.stack, self.quote, self.escape = [], None, False
        self.at_value, self.in_props, self.closed = True, False, False

    def feed(self, text):
        for k, ch in enumerate(text):
            if self.closed:
                return
            if self.quote:
                if self.escape:
                    self.escape = False
                elif self.quote == '"' and ch == "\\":
                    self.escape = True
                elif ch == self.quote:
                    self.quote, self.at_value = None, False
                continue
            if self.in_props:
                if ch in " \t":
                    self.in_props = False
                    continue
                if ch not in ",]}":
                    continue
                self.in_props = False
            if ch in " \t":
                continue
            if ch in "[{":
                self.stack.append(ch)
                self.at_value = True
            elif ch in "]}":
                if self.stack:
                    self.stack.pop()
                self.closed = not self.stack
                self.at_value = False
            elif ch == ",":
                self.at_value = True
            elif ch == ":" and (k + 1 == len(text) or text[k + 1] in " \t" or self.stack[-1:] == ["{"]):
                self.at_value = True
            elif self.at_value and ch in "'\"":
                self.quote = ch
            elif self.at_value and ch in "&!":
                self.in_props = True
            else:
                self.at_value = False


def _fold(lines):
    """Folded-scalar line joining: single breaks become spaces."""
    out = ""
    blanks = 0
    prev = None
    for line in lines:
        if line == "":
            blanks += 1
            continue
        if prev is None:
            out += "\n" * blanks
        else:
            more = prev[:1] in (" ", "\t") or line[:1] in (" ", "\t")
            if blanks == 0:
                out += "\n" if more else " "
            else:
                out += "\n" * (blanks + (1 if more else 0))
        out += line
        prev = line
        blanks = 0
    return out


class _Incomplete(Exception):
    pass


class _FlowParser:
    """Flow collections: [a, b], {a: b}, nested, with quoted or plain scalars."""

    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.doubt = False
        self.stack = []

    def skip_space(self):
        while self.pos < len(self.text) and self.text[self.pos] in " \t":
            self.pos += 1

    def peek(self):
        self.skip_space()
        if self.pos >= len(self.text):
            raise _Incomplete()
        return self.text[self.pos]

    def partial(self):
        return self.stack[0] if self.stack else None

    def value(self):
        ch = self.peek()
        if ch in "&!":
            self.doubt = True
            while self.pos < len(self.text) and self.text[self.pos] not in " \t,]}":
                self.pos += 1
            return self.value()
        if ch == "*":
            self.doubt = True
            while self.pos < len(self.text) and self.text[self.pos] not in " \t,]}":
                self.pos += 1
            return None
        if ch == "[":
            return self.seq()
        if ch == "{":
            return self.map()
        if ch in "'\"":
            end = _quoted_end(self.text, self.pos)
            if end < 0:
                raise _Incomplete()
            value = _unquote(self.text[self.pos:end + 1])
            self.pos = end + 1
            return value
        return _resolve_plain(self.plain(","))

    def plain(self, extra):
        start = self.pos
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch in "]}" or ch in extra:
                break
            if ch == ":" and (self.pos + 1 == len(self.text) or self.text[self.pos + 1] in " \t,]}"):
                break
            if ch == "#" and self.pos > start and self.text[self.pos - 1].isspace():
                break
            self.pos += 1
        return self.text[start:self.pos].strip()

    def seq(self):
        self.pos += 1
        items = []
        self.stack.append(items)
        while True:
            if self.peek() == "]":
                self.pos += 1
                break
            item = self.value()
            if self.peek() == ":":
                # [a: b] is a single-pair mapping inside a sequence.
                self.pos += 1
                item = {item: self.value()} if isinstance(item, (str, int, bool)) or item is None else item
            items.append(item)
            ch = self.peek()
            if ch == ",":
                self.pos += 1
            elif ch == "]":
                self.pos += 1
                break
            else:
                raise ValueError("bad flow sequence")
        self.stack.pop()
        return items

    def map(self):
        self.pos += 1
        result = {}
        self.stack.append(result)
        while True:
            ch = self.peek()
            if ch == "}":
                self.pos += 1
                break
            if ch in "'\"":
                key = self.value()
            elif ch in "[{":
                self.doubt = True
                key = str(self.value())
            else:
                key = _resolve_plain(self.plain(",:"))
                if not isinstance(key, (str, int, bool)) and key is not None:
                    key = str(key)
            ch = self.peek()
            value = None
            if ch == ":":
                self.pos += 1
                if self.peek() not in ",}":
                    value = self.value()
            result[key] = value
            ch = self.peek()
            if ch == ",":
                self.pos += 1
            elif ch == "}":
                self.pos += 1
                break
            else:
                raise ValueError("bad flow mapping")
        self.stack.pop()
        return result


def read_yaml(text):
    """Read the YAML subset; returns (value, certain).

    certain is False when the text uses something this reader does not
    model (anchors, aliases, tags, several documents, complex keys) or
    could not parse cleanly; value is then the best partial reading.
    """
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    reader = _YamlReader(text)
    try:
        value = reader.parse()
    except (RecursionError, IndexError, ValueError):
        return None, False
    return value, reader.certain


# ---------------------------------------------------------------- frontmatter

_FENCE_RE = re.compile(r"---[ \t]*$")
_CLOSE_RE = re.compile(r"(---|\.\.\.)[ \t]*$")


def frontmatter(text):
    """Split '---' YAML frontmatter from a Markdown text.

    Returns (data, body, certain). data is None when there is no
    frontmatter, or when it is not a mapping or never closes.
    """
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines(keepends=True)
    if not lines or not _FENCE_RE.match(lines[0].rstrip("\r\n")):
        return None, text, True
    for idx in range(1, len(lines)):
        if _CLOSE_RE.match(lines[idx].rstrip("\r\n")):
            inner = "".join(lines[1:idx])
            body = "".join(lines[idx + 1:])
            value, certain = read_yaml(inner)
            if value is None and not inner.strip():
                return {}, body, certain
            if not isinstance(value, dict):
                return None, body, False
            return value, body, certain
    return None, text, False
