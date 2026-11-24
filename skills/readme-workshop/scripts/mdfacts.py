"""Facts about a Markdown file, for checking READMEs.

facts(text, path="README.md") returns the headings with their GitHub anchors,
fenced code, links, images, badges, HTML comments, example markers, tables and
a count of prose words. It follows CommonMark and GitHub closely enough to
check a README. It never renders anything and uses only the standard library.
"""

from __future__ import annotations

import bisect
import html
import re
import unicodedata

BADGE_RE = re.compile(
    r"shields\.io|badge|badgen|/workflows/|codecov|coveralls|img\.shields|"
    r"star-history|deepwiki\.com/badge|api\.netlify|vercel\.com/button|ko-fi\.com/img|"
    r"buymeacoffee|liberapay|opencollective\.com/[^/]+/(backers|sponsors)", re.I)
INSTALL_RE = re.compile(r"\b(install|get(ting)? started|quick ?start|setup|set up|download)", re.I)
WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")
ATX_RE = re.compile(r"^ {0,3}(#{1,6})(?=[ \t]|$)[ \t]*(.*?)(?:[ \t]+#+)?[ \t]*$")
SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
HR_RE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
LIST_RE = re.compile(r"^( *)([-+*]|\d{1,9}[.)])(?:( +)|$)")
FENCE_RE = re.compile(r"^( *)(`{3,}|~{3,})(.*)$")
TABLE_SEP_RE = re.compile(r"^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")
REFDEF_RE = re.compile(r"^ {0,3}\[([^\]^][^\]]*)\]:[ \t]*(?:<([^>]*)>|(\S+))"
                       r"(?:[ \t]+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?[ \t]*$")
MARKER_RE = re.compile(r"^\s*<!--\s*matches:\s*([^\s#]+)(?:#L([0-9]+)(?:-L?([0-9]+))?)?\s*-->\s*$")
QUOTE_RE = re.compile(r" {0,3}> ?")
HTML1_RE = re.compile(r"^ {0,3}<(pre|script|style|textarea)(?=[\s>]|$)", re.I)
HTML6_RE = re.compile(
    r"^ {0,3}</?(address|article|aside|blockquote|body|caption|center|details|dialog|dd|div|"
    r"dl|dt|fieldset|figcaption|figure|footer|form|h[1-6]|header|hr|html|li|main|nav|ol|p|"
    r"picture|section|source|summary|table|tbody|td|tfoot|th|thead|tr|ul)(?=[\s/>]|$)", re.I)
HTML7_RE = re.compile(r"^ {0,3}(?:<[A-Za-z][\w-]*(?:\s[^<>]*)?/?>|</[A-Za-z][\w-]*\s*>)\s*$")
TAG_RE = re.compile(r"</?([A-Za-z][\w-]*)(\s[^<>]*)?/?>")
ATTR_RE = re.compile(r"([\w:-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'>]+))")
AUTOLINK_RE = re.compile(r"<([A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*|[\w.+-]+@[\w-]+(?:\.[\w-]+)+)>")
BARE_URL_RE = re.compile(r"(?<![\w/@])(?:https?://|www\.)[^\s<>()\[\]]*[^\s<>()\[\].,;:!?'\"*_~]")
ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]*|#\d+|#x[0-9A-Fa-f]+);")
ESCAPE_RE = re.compile(r"\\([!-/:-@\[-`{-~])|(&(?:[A-Za-z][A-Za-z0-9]{0,31}|#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6});)")
SHORTCODE_RE = re.compile(r":[a-z0-9_+-]+:")
TOC_HEADING_RE = re.compile(r"^(table of )?contents$|^toc$")
TEXT_KINDS = ("text", "heading", "table")


def facts(text, *, path="README.md"):
    """Return a dict of facts about the Markdown in `text` (see the module doc)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    b = _blocks(lines)
    inl = _inline(lines, b["kinds"], b["refdefs"])
    headings = b["headings"]
    for h, anchor in zip(headings, _anchors([h["text"] for h in headings])):
        h["anchor"] = anchor
    ids = inl["ids"] | {_slug(SHORTCODE_RE.sub(lambda m: m.group(0).strip(":"), h["text"]))
                        for h in headings if SHORTCODE_RE.search(h["text"])}
    second = headings[1]["line"] if len(headings) > 1 else len(lines) + 1
    toc_items = {l["line"] for l in inl["links"] if l["target"].startswith("#") and l["line"] < second
                 and LIST_RE.match(lines[l["line"] - 1].lstrip(" >"))}
    toc_named = any(TOC_HEADING_RE.match(re.sub(r"[^a-z ]", "", h["text"].lower()).strip()) for h in headings)
    images = inl["images"]
    return {
        "path": path,
        "lines": len(lines),
        "words": inl["words"],
        "headings": headings,
        "fences": b["fences"],
        "links": inl["links"],
        "images": images,
        "badges": [{"line": i["line"], "src": i["src"]} for i in images if BADGE_RE.search(i["src"])],
        "comments": sorted(b["comments"] + inl["comments"], key=lambda c: c["line"]),
        "markers": b["markers"],
        "install_line": next((h["line"] for h in headings if INSTALL_RE.search(h["text"])), None),
        "first_code_line": b["fences"][0]["line"] if b["fences"] else None,
        "first_image_line": min((i["line"] for i in images), default=None),
        "toc": len(toc_items) >= 4 or toc_named,
        # Beyond the contract: what the checker needs to read the page.
        "tables": b["tables"],
        "ids": sorted(ids),
        "refdefs": b["refdefs"],
        "prose": inl["prose"],
        "line_kinds": b["kinds"],
    }


def _indent(line):
    """Columns of leading whitespace, with tabs to the next multiple of four."""
    return len(line[: len(line) - len(line.lstrip(" \t"))].expandtabs(4))


def _dedent(line, cols):
    """Remove up to `cols` columns of leading whitespace."""
    k = col = 0
    while k < len(line) and col < cols and line[k] in " \t":
        col = (col // 4 + 1) * 4 if line[k] == "\t" else col + 1
        k += 1
    return line[k:]


def _quote_marks(line):
    """Where each block-quote marker at the start of a line ends: '> > x' gives [2, 4]."""
    ends, m = [], QUOTE_RE.match(line)
    while m:
        ends.append(m.end())
        m = QUOTE_RE.match(line, m.end())
    return ends


def _blocks(lines):
    """Classify each line and collect block-level facts.

    Lines inside block quotes are classified by what follows their > marks,
    so a quoted heading or fence counts as one; line numbers stay the same.
    """
    n = len(lines)
    kinds = ["blank"] * n
    out = {"kinds": kinds, "headings": [], "fences": [], "comments": [], "markers": [],
           "tables": [], "refdefs": {}}
    marks = [_quote_marks(l) for l in lines]
    depth = [len(m) for m in marks]
    content = [l[m[-1]:] if m else l for l, m in zip(lines, marks)]
    list_indent, para, para_start, para_list, para_depth = None, False, 0, False, 0
    i = 0
    if n and lines[0].strip() == "---":  # front matter
        end = next((j for j in range(1, n) if lines[j].strip() in ("---", "...")), None)
        if end is not None:
            kinds[: end + 1] = ["raw"] * (end + 1)
            i = end + 1
    while i < n:
        line = content[i]
        if not line.strip():
            para, i = False, i + 1
            continue
        indent = _indent(line)
        lm = LIST_RE.match(line)
        gap = 0
        if lm:
            gap = len(lm.group(3) or " ")
            list_indent = len(lm.group(1)) + len(lm.group(2)) + (gap if gap <= 4 else 1)
        elif list_indent is not None and indent < list_indent and not para:
            list_indent = None
        nest = list_indent if list_indent is not None and indent >= list_indent and not lm else 0
        sub, rel = line.expandtabs(4)[nest:], indent - nest
        if rel >= 4 and not para and not lm:  # indented code
            j = i
            while j < n and depth[j] == depth[i] and (not content[j].strip() or _indent(content[j]) >= nest + 4):
                j += 1
            while j > i and not content[j - 1].strip():
                j -= 1
            kinds[i:j] = ["code"] * (j - i)
            i = j
            continue
        # A fence opens where a block can start: after a list item's marker too. Its closing
        # fence is placed relative to the item's content column (or the quote), like the opener.
        fm, at, base = None, indent, nest
        if lm and gap <= 4:
            fm, at, base = FENCE_RE.match(line.expandtabs(4)[list_indent:]), list_indent, list_indent
        if fm is None and rel <= 3:
            fm, at, base = FENCE_RE.match(sub), indent, nest
        if fm and not (fm.group(2)[0] == "`" and "`" in fm.group(3)):
            stop = _fence(lines, marks, i, at, base, fm, out)
            mm = MARKER_RE.match(content[i - 1]) if i and kinds[i - 1] == "comment" else None
            if mm:
                start = _line_number(mm.group(2))
                out["markers"].append({"line": i, "path": mm.group(1), "start": start,
                                       "end": _line_number(mm.group(3)) or start, "fence": len(out["fences"]) - 1})
            i, para = stop, False
            continue
        if rel <= 3 and sub.lstrip().startswith("<!--"):
            j = i
            while j < n - 1 and "-->" not in content[j][(line.index("<!--") + 4) if j == i else 0:]:
                j += 1
            chunk = "\n".join(content[i: j + 1])
            body = chunk[chunk.index("<!--") + 4:]
            out["comments"].append({"line": i + 1, "text": body.split("-->")[0].strip()})
            kinds[i: j + 1] = ["comment"] * (j + 1 - i)
            i, para = j + 1, False
            continue
        block = None
        m1 = HTML1_RE.match(sub)
        if m1:
            close = "</%s>" % m1.group(1).lower()
            j = i
            while j < n - 1 and close not in content[j].lower():
                j += 1
            block = ("raw", j + 1)
        elif HTML6_RE.match(sub) or (HTML7_RE.match(sub) and not para):
            j = i
            while j < n and content[j].strip():
                j += 1
            block = ("html", j)
        if block:
            kinds[i: block[1]] = [block[0]] * (block[1] - i)
            i, para = block[1], False
            continue
        am = ATX_RE.match(sub)
        if am:
            out["headings"].append({"level": len(am.group(1)), "text": plain(am.group(2)), "line": i + 1})
            kinds[i], para, i = "heading", False, i + 1
            continue
        if SETEXT_RE.match(sub) and para and not para_list and depth[i] == para_depth:
            raw = " ".join(l.strip() for l in content[para_start:i])
            level = 1 if sub.strip()[0] == "=" else 2
            out["headings"].append({"level": level, "text": plain(raw), "line": para_start + 1})
            kinds[para_start: i + 1] = ["heading"] * (i + 1 - para_start)
            para, i = False, i + 1
            continue
        if HR_RE.match(sub):
            kinds[i], para, i = "hr", False, i + 1
            continue
        if re.match(r"^ {0,3}\[\^[^\]]+\]:", sub):  # a footnote ends the paragraph before it
            kinds[i], para, i = "text", False, i + 1
            continue
        rm = REFDEF_RE.match(sub)
        if rm and not para:
            label = " ".join(rm.group(1).split()).casefold()
            out["refdefs"].setdefault(label, {"target": rm.group(2) if rm.group(2) is not None
                                              else rm.group(3), "line": i + 1})
            kinds[i], i = "refdef", i + 1
            continue
        if "|" in sub and i + 1 < n and "|" in content[i + 1] and TABLE_SEP_RE.match(content[i + 1][nest:]) \
                and len(_cells(sub)) == len(_cells(content[i + 1])):
            table = {"line": i + 1, "header": _cells(sub), "rows": []}
            kinds[i], kinds[i + 1] = "table", "tablesep"
            j = i + 2
            while j < n and content[j].strip() and "|" in content[j]:
                table["rows"].append({"line": j + 1, "cells": _cells(content[j])})
                kinds[j], j = "table", j + 1
            out["tables"].append(table)
            i, para = j, False
            continue
        if not para:
            para_start, para_list, para_depth = i, bool(lm) or list_indent is not None, depth[i]
        kinds[i], para, i = "text", True, i + 1
    return out


def _fence(lines, marks, i, indent, base, fm, out):
    """Record the fence opening on line i at column indent; return the index after it.

    base is the column its container's content starts at (a list item's, or 0).
    A closing fence is indented at most three columns past base, wherever the
    opener sits. A fence inside a block quote holds the quote's lines with
    their > marks removed, and ends where the quote does if no fence line
    closes it first. end_line is the block's last line, or None when it runs
    to the end of the page.
    """
    n, ch, size, level = len(lines), fm.group(2)[0], len(fm.group(2)), len(marks[i])
    close = re.compile(r"^[ \t]*%s{%d,}[ \t]*$" % (re.escape(ch), size))

    def inside(j):  # line j without this quote's marks, or None once the quote has ended
        if len(marks[j]) < level:
            return None
        return lines[j][marks[j][level - 1]:] if level else lines[j]

    j = i + 1
    while j < n:
        line = inside(j)
        if line is None or (close.match(line) and _indent(line) <= base + 3):
            break
        j += 1
    body = [_dedent(inside(k), indent) for k in range(i + 1, j)]
    if j == n:
        end_line, stop = None, n
    elif inside(j) is None:
        end_line, stop = j, j
    else:
        end_line, stop = j + 1, j + 1
    out["fences"].append({"line": i + 1, "end_line": end_line, "info": fm.group(3).strip(), "text": "\n".join(body)})
    out["kinds"][i:stop] = ["fence"] * (stop - i)
    return stop


def _line_number(digits):
    """A marker's line number; any number of digits, without converting thousands of them."""
    if not digits:
        return None
    return int(digits) if len(digits) <= 9 else 10 ** 9


def _cells(row):
    """Split a table row into cells, keeping pipes inside code spans or escaped."""
    row = row.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
    cells, cur, code = [], [], False
    for k, ch in enumerate(row):
        if ch == "`":
            code = not code
        if ch == "|" and not code and (k == 0 or row[k - 1] != "\\"):
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    return cells + ["".join(cur).strip()]


# Code spans stand in the heading text as CODE_OPEN + number + CODE_CLOSE while the markup
# around them is removed; both count as punctuation, as the backticks they replace do.
# Neither character can come out of a character reference (&#0; decodes to U+FFFD, &#1;
# to nothing) or a backslash escape, so the page's own text never names a code span.
CODE_OPEN, CODE_CLOSE = "\x00", "\x01"
_PLACEHOLDER_RE = re.compile(CODE_OPEN + r"([0-9]+)" + CODE_CLOSE)


def plain(raw):
    """Heading or cell text as GitHub shows it: markup and HTML comments gone, code kept literally."""
    codes, parts, pos = [], [], 0
    spans, k, comment = _code_spans(raw), 0, _next_comment(raw, 0)
    while True:  # left to right: whichever of a code span and a comment starts first wins
        while k < len(spans) and spans[k][0] < pos:
            k += 1
        if comment and comment[0] < pos:
            comment = _next_comment(raw, pos)
        span = spans[k] if k < len(spans) else None
        if comment and (span is None or comment[0] < span[0]):
            parts.append(_no_markers(raw[pos:comment[0]]))
            pos = comment[1]
        elif span:
            parts.append(_no_markers(raw[pos:span[0]]))
            parts.append("%s%d%s" % (CODE_OPEN, len(codes), CODE_CLOSE))
            codes.append(span[2].strip())
            pos = span[1]
        else:
            parts.append(_no_markers(raw[pos:]))
            break
    text = _PLACEHOLDER_RE.sub(lambda m: codes[int(m.group(1))] if int(m.group(1)) < len(codes) else "",
                               _unmark("".join(parts)))
    return _no_markers(text).strip()


def _no_markers(s):
    return s.replace(CODE_OPEN, "").replace(CODE_CLOSE, "")


def _next_comment(raw, pos):
    """(start, end) of the first HTML comment at or after pos, or None; <!--> and <!---> count."""
    start = raw.find("<!--", pos)
    if start < 0:
        return None
    if raw.startswith(">", start + 4) or raw.startswith("->", start + 4):
        return start, raw.index(">", start + 4) + 1
    close = raw.find("-->", start + 4)
    return (start, close + 3) if close >= 0 else None  # none closes here, so none after it does


def _code_spans(s):
    """(start, end, content) of each code span: a backtick run that is not escaped, up to
    the next run of the same length (inside the span, backslashes are literal)."""
    runs = {}
    for m in re.finditer(r"`+", s):
        runs.setdefault(len(m.group(0)), []).append(m.start())
    spans, pos = [], 0
    for m in re.finditer(r"\\.|`+", s, re.S):
        if m.start() < pos or m.group(0)[0] == "\\":
            continue
        size, after = len(m.group(0)), m.end()
        same = runs.get(size, ())
        k = bisect.bisect_left(same, after)
        if k < len(same):
            spans.append((m.start(), same[k] + size, s[after:same[k]]))
            pos = same[k] + size
    return spans


def _unmark(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])", r"\1", s)
    s = re.sub(r"</?[A-Za-z][^<>]*>", "", s)
    return _unescape(_strip_emphasis(s))


def _punct(ch):
    return ch in (CODE_OPEN, CODE_CLOSE) or unicodedata.category(ch)[0] in "PS"


class _Run:
    """A run of * or _; the characters from lo to hi are the ones not yet used as emphasis."""

    __slots__ = ("start", "end", "lo", "hi", "ch", "opens", "closes")

    def __init__(self, start, end, ch, opens, closes):
        self.start, self.end, self.lo, self.hi, self.ch = start, end, start, end, ch
        self.opens, self.closes = opens, closes

    @property
    def size(self):
        return self.end - self.start

    @property
    def left(self):
        return self.hi - self.lo


def _strip_emphasis(s):
    """s without the * and _ that pair up as emphasis; a lone one stays, as GitHub shows it.

    CommonMark's delimiter-run rules: flanking decides which runs can open
    or close, each closer takes the nearest opener of the same character,
    and the openers a closer has passed over are not tried again.
    """
    runs = []
    for m in re.finditer(r"\\.|\*+|_+", s, re.S):
        if m.group(0)[0] == "\\":
            continue
        a, b = m.span()
        before, after = s[a - 1: a] or " ", s[b: b + 1] or " "
        left = not after.isspace() and (not _punct(after) or before.isspace() or _punct(before))
        right = not before.isspace() and (not _punct(before) or after.isspace() or _punct(after))
        if m.group(0)[0] == "*":
            runs.append(_Run(a, b, "*", left, right))
        else:
            runs.append(_Run(a, b, "_", left and (not right or _punct(before)), right and (not left or _punct(after))))
    stack, bottom = [], {}
    for run in runs:
        key = (run.ch, run.opens, run.size % 3)
        while run.closes and run.left:
            found = None
            for k in range(len(stack) - 1, min(bottom.get(key, 0), len(stack)) - 1, -1):
                opener = stack[k]
                odd = (opener.closes or run.opens) and (opener.size + run.size) % 3 == 0 \
                    and not (opener.size % 3 == 0 and run.size % 3 == 0)
                if opener.ch == run.ch and not odd:
                    found = k
                    break
            if found is None:
                bottom[key] = len(stack)
                break
            opener = stack[found]
            use = 2 if opener.left >= 2 and run.left >= 2 else 1
            opener.hi -= use
            run.lo += use
            del stack[found + (opener.left > 0):]  # runs between the pair stay as text
            bottom = {k: min(v, len(stack)) for k, v in bottom.items()}
        if run.opens and run.left:
            stack.append(run)
    out, pos = [], 0
    for run in runs:
        out += [s[pos:run.start], s[run.lo:run.hi]]
        pos = run.end
    out.append(s[pos:])
    return "".join(out)


def _slug(text):
    """GitHub's anchor for a heading text (github-slugger rules)."""
    out = []
    for ch in text.lower():
        if ch == " ":
            out.append("-")
        elif ch in "-_" or unicodedata.category(ch)[0] in "LNM":
            out.append(ch)
    return "".join(out)


def _anchors(texts):
    seen, result = {}, []
    for text in texts:
        base = _slug(SHORTCODE_RE.sub("", text))
        slug = base
        while slug in seen:
            seen[base] += 1
            slug = "%s-%d" % (base, seen[base])
        seen[slug] = 0
        result.append(slug)
    return result


def _inline(lines, kinds, refdefs):
    """Links, images, comments, ids and prose words from text and HTML lines."""
    kept = [l if kinds[k] in TEXT_KINDS or kinds[k] == "html" else "" for k, l in enumerate(lines)]
    starts = [0]
    for l in kept:
        starts.append(starts[-1] + len(l) + 1)
    doc = "\n".join(kept)

    def line_of(pos):
        return bisect.bisect_right(starts, pos)

    def is_text(pos):
        return kinds[line_of(pos) - 1] in TEXT_KINDS

    chars, spans, comments = list(doc), [], []

    def mask(a, b):
        for k in range(a, b):
            if chars[k] != "\n":
                chars[k] = " "

    # Backtick runs by length, and paragraph ends, so each code span is found by lookup.
    runs = {}
    for m in re.finditer(r"`+", doc):
        runs.setdefault(len(m.group(0)), []).append(m.start())
    breaks = [m.start() for m in re.finditer(r"\n\n", doc)] + [len(doc)]
    i, comments_open = 0, True
    while i < len(doc):
        if doc[i] == "\\":
            i += 2
        elif comments_open and doc.startswith("<!--", i):
            j = doc.find("-->", i + 4)
            if j < 0:  # no comment closes after here: the rest is plain text
                comments_open = False
                continue
            comments.append({"line": line_of(i), "text": doc[i + 4:j].strip()})
            mask(i, j + 3)
            i = j + 3
        elif doc[i] == "`" and is_text(i):
            k = i
            while k < len(doc) and doc[k] == "`":
                k += 1
            same = runs.get(k - i, ())  # after an escaped tick the run may be shorter than any other
            nxt = bisect.bisect_left(same, k)
            close = same[nxt] if nxt < len(same) else None
            if close is not None and close < breaks[bisect.bisect_left(breaks, k)]:
                spans.append(doc[k:close])
                mask(i, close + k - i)
                i = close + k - i
            else:
                i = k
        else:
            i += 1
    masked = "".join(chars)
    links, images = [], []
    _scan(masked, 0, len(masked), _bracket_pairs(masked), refdefs, is_text, line_of, links, images, mask)
    ids = set()
    for m in TAG_RE.finditer("".join(chars)):
        name = m.group(1).lower()
        attrs = {a.group(1).lower(): next(g for g in a.groups()[1:] if g is not None)
                 for a in ATTR_RE.finditer(m.group(2) or "")}
        line = line_of(m.start())
        if name == "a" and "href" in attrs:
            after = masked[m.end(): m.end() + 500]
            text = TAG_RE.sub("", after.split("</a>")[0]).strip() if "</a>" in after else ""
            links.append({"line": line, "text": text, "target": _unescape(attrs["href"], False).strip(), "kind": "html"})
        elif name == "img" and "src" in attrs:
            images.append({"line": line, "alt": attrs.get("alt", ""), "src": _unescape(attrs["src"], False).strip(),
                           "kind": "html"})
        elif re.fullmatch(r"h[1-6]", name) and m.group(0)[1] != "/":
            ids.add(_slug(plain(TAG_RE.sub("", masked[m.end(): m.end() + 500].split("</")[0]))))
        ids.update(attrs[k] for k in ("id", "name") if k in attrs and (k == "id" or name == "a"))
        mask(m.start(), m.end())
    prose = "".join(chars)
    for m in AUTOLINK_RE.finditer(prose):
        if is_text(m.start()):
            links.append({"line": line_of(m.start()), "text": m.group(1), "target": m.group(1), "kind": "autolink"})
        mask(m.start(), m.end())
    prose = "".join(chars)
    for m in BARE_URL_RE.finditer(prose):
        if is_text(m.start()):
            links.append({"line": line_of(m.start()), "text": m.group(0), "target": m.group(0), "kind": "autolink"})
        mask(m.start(), m.end())
    for m in ENTITY_RE.finditer(doc):
        mask(m.start(), m.end())
    prose_lines = "".join(chars).split("\n")
    words = sum(len(WORD_RE.findall(p)) for p in prose_lines) + sum(len(WORD_RE.findall(s)) for s in spans)
    links.sort(key=lambda l: l["line"])
    images.sort(key=lambda l: l["line"])
    return {"links": links, "images": images, "comments": comments, "ids": ids,
            "words": words, "prose": prose_lines}


def _unescape(s, backslashes=True):
    """s with Markdown backslash escapes and character references decoded (references need their ;)."""
    def one(m):
        if m.group(1) is not None:
            return m.group(1) if backslashes else m.group(0)
        return html.unescape(m.group(2))
    return ESCAPE_RE.sub(one, s)


def _bracket_pairs(s):
    """Map each [ to the ] that closes it, in one pass; brackets never pair across a blank line."""
    pairs, stack, i = {}, [], 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 1
        elif c == "[":
            stack.append(i)
        elif c == "]" and stack:
            pairs[stack.pop()] = i
        elif c == "\n":
            nxt = s.find("\n", i + 1)
            if nxt > i and not s[i + 1: nxt].strip():
                stack = []
        i += 1
    return pairs


GAP = r"[ \t]*(?:\n[ \t]*)?"  # spaces with at most one line break; written so spaces never backtrack
DEST_RE = re.compile(r"\(" + GAP + r"(?:<((?:[^<>\n\\]|\\.)*)>|((?:[^\s()\\]|\\.|\((?:[^\s()\\]|\\.)*\))*))"
                     r"(?:" + GAP + r"(?:\"[^\"]*\"|'[^']*'|\([^()]*\)))?" + GAP + r"\)")
LABEL_MAX = 999  # a reference label is at most this long (CommonMark)


def _scan(s, start, end, pairs, refdefs, is_text, line_of, links, images, mask, depth=0):
    """Find Markdown links and images in s[start:end]; blank their syntax with mask()."""
    i = start
    while i < end:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        img = c == "!" and s.startswith("[", i + 1)
        if (c == "[" or img) and is_text(i):
            ob = i + 1 if img else i
            cb = pairs.get(ob)
            if cb is not None and cb < end and not s.startswith("^", ob + 1):
                m = DEST_RE.match(s, cb + 1)
                found = ((m.group(1) if m.group(1) is not None else m.group(2)), m.end()) if m else None
                kind = "inline"
                if found is None:
                    j, ref = cb + 1, (ob + 1, cb)
                    rb = pairs.get(j) if s.startswith("[", j) else None
                    if rb is not None:
                        ref, j = ((j + 1, rb) if rb > j + 1 else ref), rb + 1
                    # Labels are sliced only when short enough to name a reference, so nested brackets stay cheap.
                    target = refdefs.get(" ".join(s[ref[0]: ref[1]].split()).casefold()) \
                        if ref[1] - ref[0] <= LABEL_MAX else None
                    found = (target["target"], j) if target and not s.startswith(":", j) else None
                    kind = "reference"
                if found:
                    dest, j = found
                    dest, label = _unescape(dest.strip()), s[ob + 1: cb]
                    record = {"line": line_of(i), "kind": "markdown" if img else kind}
                    if img:
                        record.update(alt=" ".join(label.split()), src=dest)
                        images.append(record)
                        mask(i, j)
                    else:
                        record.update(text=" ".join(label.split()), target=dest)
                        links.append(record)
                        if depth < 4:  # images inside link text, such as a linked badge
                            _scan(s, ob + 1, cb, pairs, refdefs, is_text, line_of, links, images, mask, depth + 1)
                        mask(i, ob + 1)
                        mask(cb, j)
                    i = j
                    continue
        i += 1
