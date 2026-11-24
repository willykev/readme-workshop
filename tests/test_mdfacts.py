"""Tests for mdfacts: the Markdown reader the checker stands on."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "readme-workshop", "scripts"))

import mdfacts  # noqa: E402


def facts(text):
    return mdfacts.facts(text)


def targets(f, kind=None):
    return [l["target"] for l in f["links"] if kind is None or l["kind"] == kind]


class Headings(unittest.TestCase):
    def test_levels_lines_and_closing_hashes(self):
        f = facts("# Title #\n\nText\n\n### Deep ###\n")
        self.assertEqual([(h["level"], h["text"], h["line"]) for h in f["headings"]],
                         [(1, "Title", 1), (3, "Deep", 5)])

    def test_setext_headings(self):
        f = facts("Title\n=====\n\nSub\n---\n\nText\n\n---\n")
        self.assertEqual([(h["level"], h["text"]) for h in f["headings"]], [(1, "Title"), (2, "Sub")])

    def test_list_item_then_dashes_is_not_a_heading(self):
        self.assertEqual(facts("- item\n---\n")["headings"], [])

    def test_hash_without_space_is_not_a_heading(self):
        self.assertEqual(facts("#hashtag\n")["headings"], [])

    def test_duplicates_get_numbered_anchors(self):
        f = facts("# A\n## A\n## A\n## Foo\n## Foo-1\n## Foo\n")
        self.assertEqual([h["anchor"] for h in f["headings"]], ["a", "a-1", "a-2", "foo", "foo-1", "foo-2"])

    def test_punctuation_emoji_and_unicode(self):
        f = facts("## What's new?\n## 🚀 Launch\n## Café & Crème\n## C++ / C#\n"
                  "## `--json` output\n## Über Größe\n## 日本語\n## Quick start — a user\n"
                  "## **Bold** and [link](x.md)\n## snake_case_name\n")
        self.assertEqual([h["anchor"] for h in f["headings"]], [
            "whats-new", "-launch", "café--crème", "c--c", "--json-output", "über-größe", "日本語",
            "quick-start--a-user", "bold-and-link", "snake_case_name"])
        self.assertEqual(f["headings"][1]["text"], "🚀 Launch")

    def test_emoji_shortcode_anchor_accepts_both_spellings(self):
        f = facts("## :rocket: Launch\n")
        self.assertEqual(f["headings"][0]["anchor"], "-launch")
        self.assertIn("rocket-launch", f["ids"])

    def test_html_ids_and_names_are_anchors(self):
        f = facts('<a name="legacy"></a>\n\nText <span id="here">x</span>\n')
        self.assertIn("legacy", f["ids"])
        self.assertIn("here", f["ids"])

    def test_emphasis_marks_go_only_in_pairs(self):
        f = facts("## _config.yml\n## __init__.py\n## _emph_ word\n## *star\n## a_b_c and _x_\n"
                  "## **bold** _(optional)_\n## _a `b` c_\n## \\_kept\\_\n## ***both*** **un*\n")
        self.assertEqual([h["text"] for h in f["headings"]], [
            "_config.yml", "init.py", "emph word", "*star", "a_b_c and x", "bold (optional)", "a b c", "_kept_",
            "both *un"])
        self.assertEqual([h["anchor"] for h in f["headings"]][:3], ["_configyml", "initpy", "emph-word"])

    def test_code_in_headings_follows_backslashes(self):
        f = facts("## \\`not code\\`\n## `a\\` b\n## x \\``y`\n## `&amp;` &amp;\n")
        self.assertEqual([h["text"] for h in f["headings"]], ["`not code`", "a\\ b", "x `y", "&amp; &"])

    def test_headings_and_fences_inside_block_quotes(self):
        f = facts("See [it](#install).\n\n> ## Install\n> Run it.\n>\n> > ### Deeper\n\n"
                  "> ~~~md\n> [x](gone.md)\n> ~~~\n\n> ```sh\n> make\n\nAfter [y](y.md)\n")
        self.assertEqual([(h["level"], h["text"], h["line"], h["anchor"]) for h in f["headings"]],
                         [(2, "Install", 3, "install"), (3, "Deeper", 6, "deeper")])
        self.assertEqual([(x["line"], x["end_line"], x["text"]) for x in f["fences"]],
                         [(8, 10, "[x](gone.md)"), (12, 13, "make")])
        self.assertEqual(targets(f), ["#install", "y.md"])
        self.assertEqual(f["line_kinds"][4], "blank")

    def test_html_comments_are_not_part_of_the_anchor(self):
        f = facts("## Install <!-- omit in toc -->\n## `<!-- x -->` code\n## A <!-- `b` --> c\n"
                  "See [i](#install).\n")
        self.assertEqual([h["anchor"] for h in f["headings"]], ["install", "---x----code", "a--c"])
        self.assertEqual([h["text"] for h in f["headings"]][:2], ["Install", "<!-- x --> code"])

    def test_character_references_never_reach_code_spans(self):
        # References that decode to characters the heading reader once used for its own markers.
        f = facts("## a &#xe000;5&#xe001; b\n## `x` &#xe000;0&#xe001;\n## &#0;1&#1; `y`\n## \x00`z`\x01\n")
        self.assertEqual([h["anchor"] for h in f["headings"]], ["a-5-b", "x-0", "1-y", "z"])
        self.assertEqual(f["headings"][1]["text"], "x \ue0000\ue001")

    def test_code_block_lines_keep_their_quote_marks(self):
        f = facts("```\n> not a quote\n> # nor a heading\n```\n")
        self.assertEqual(f["fences"][0]["text"], "> not a quote\n> # nor a heading")
        self.assertEqual(f["headings"], [])


class Fences(unittest.TestCase):
    def test_crlf(self):
        f = facts("# Title\r\n\r\nSee [a](b.md).\r\n\r\n```sh\r\nls\r\n```\r\n")
        self.assertEqual(f["lines"], 7)
        self.assertEqual(f["fences"], [{"line": 5, "end_line": 7, "info": "sh", "text": "ls"}])
        self.assertEqual(f["links"][0]["line"], 3)

    def test_tilde_fence_holds_backticks(self):
        f = facts("~~~python\nprint(1)\n```\n~~~\n")
        self.assertEqual(len(f["fences"]), 1)
        self.assertEqual(f["fences"][0]["info"], "python")
        self.assertEqual(f["fences"][0]["text"], "print(1)\n```")

    def test_four_backticks_hold_three(self):
        f = facts("````md\n```sh\nls\n```\n````\n\n# After\n")
        self.assertEqual([(x["line"], x["end_line"]) for x in f["fences"]], [(1, 5)])
        self.assertIn("```sh", f["fences"][0]["text"])
        self.assertEqual([h["text"] for h in f["headings"]], ["After"])

    def test_fence_inside_a_list(self):
        f = facts("1. Step one:\n\n   ```sh\n   make\n     indented\n   ```\n2. Next\n")
        self.assertEqual(f["fences"][0]["end_line"], 6)
        self.assertEqual(f["fences"][0]["text"], "make\n  indented")

    def test_fence_inside_a_nested_list(self):
        f = facts("- a\n  - b\n\n    ```sh\n    run [x](y.md)\n    ```\n")
        self.assertEqual(len(f["fences"]), 1)
        self.assertEqual(f["links"], [])

    def test_fence_on_a_list_items_first_line(self):
        for text in ("- ```sh\n  make\n  ```\n\nAfter [x](y.md)\n", "1. ```sh\n   make\n   ```\n\nAfter [x](y.md)\n",
                     "> - ```sh\n>   make\n>   ```\n\nAfter [x](y.md)\n"):
            with self.subTest(text=text):
                f = facts(text)
                self.assertEqual([(x["line"], x["end_line"], x["info"], x["text"]) for x in f["fences"]],
                                 [(1, 3, "sh", "make")])
                self.assertEqual(f["line_kinds"][:3], ["fence"] * 3)
                self.assertEqual(targets(f), ["y.md"])

    def test_closing_fence_indent_is_counted_from_its_container(self):
        # A closing fence sits at most three columns in from its list item or quote, wherever the opener sits.
        cases = {"  ```\n  x\n     ```\n  ```\n": (4, "x\n   ```"),
                 "- a\n\n    ```\n    x\n       ```\n    ```\n": (6, "x\n   ```"),
                 ">   ```\n>   x\n>      ```\n>   ```\n": (4, "x\n   ```"),
                 "- a\n\n  ```\n  x\n     ```\n": (5, "x")}
        for text, (end, body) in cases.items():
            with self.subTest(text=text):
                f = facts(text)
                self.assertEqual([(x["end_line"], x["text"]) for x in f["fences"]], [(end, body)])

    def test_unclosed_fence_runs_to_the_end(self):
        f = facts("Text\n\n```sh\nls\n\n# not a heading\n[x](y.md)\n")
        self.assertIsNone(f["fences"][0]["end_line"])
        self.assertEqual(f["headings"], [])
        self.assertEqual(f["links"], [])

    def test_backtick_fence_info_cannot_hold_backticks(self):
        self.assertEqual(facts("``` a`b\n")["fences"], [])

    def test_indented_code_is_not_prose(self):
        f = facts("Para\n\n    [x](missing.md)\n\nAfter\n")
        self.assertEqual(f["links"], [])
        self.assertEqual(f["words"], 2)

    def test_first_code_line(self):
        self.assertEqual(facts("a\n\n```\nx\n```\n")["first_code_line"], 3)
        self.assertIsNone(facts("a\n")["first_code_line"])


class Links(unittest.TestCase):
    def test_inline_links_with_titles_and_angle_brackets(self):
        f = facts('[a](a.md "Title") [b](<b c.md>) [c](c.md#part) [d](https://x.org/(y))\n')
        self.assertEqual(targets(f), ["a.md", "b c.md", "c.md#part", "https://x.org/(y)"])
        self.assertEqual({l["kind"] for l in f["links"]}, {"inline"})

    def test_link_split_over_two_lines(self):
        f = facts("See [the whole\nguide](docs/guide.md) now.\n")
        self.assertEqual(f["links"][0]["text"], "the whole guide")
        self.assertEqual(f["links"][0]["line"], 1)

    def test_reference_links_and_images(self):
        f = facts("[guide][g], [Guide][], [g] and [none][missing]. ![logo][l]\n\n"
                  "[g]: docs/guide.md\n[GUIDE]: <docs/guide.md>\n[l]: logo.png \"Logo\"\n")
        refs = [(l["text"], l["target"]) for l in f["links"] if l["kind"] == "reference"]
        self.assertEqual(refs, [("guide", "docs/guide.md"), ("Guide", "docs/guide.md"), ("g", "docs/guide.md")])
        self.assertEqual([(i["alt"], i["src"], i["kind"]) for i in f["images"]], [("logo", "logo.png", "markdown")])
        self.assertIn("g", f["refdefs"])

    def test_autolinks(self):
        f = facts("<https://example.com> and https://x.org/y. Mail <me@example.com>.\n")
        self.assertEqual(targets(f, "autolink"), ["https://example.com", "me@example.com", "https://x.org/y"])

    def test_html_img_and_a(self):
        f = facts('<p align="center"><img src="a.png" alt="A chart" width="300"></p>\n\n'
                  'Read <a href="docs/x.md">the guide</a>.\n')
        self.assertEqual([(i["src"], i["alt"], i["kind"]) for i in f["images"]], [("a.png", "A chart", "html")])
        self.assertEqual([(l["target"], l["text"], l["kind"]) for l in f["links"]],
                         [("docs/x.md", "the guide", "html")])

    def test_html_with_full_addresses(self):
        f = facts('<p align="center">\n  <a href="https://ci.example.com"><img src="https://img.shields.io/b/ci" '
                  'alt="CI"></a> see https://bare.example.com\n</p>\n')
        self.assertEqual([i["src"] for i in f["images"]], ["https://img.shields.io/b/ci"])
        self.assertEqual(len(f["badges"]), 1)
        self.assertEqual(targets(f), ["https://ci.example.com"])
        self.assertEqual(f["words"], 1)

    def test_badge_inside_a_link(self):
        f = facts("[![CI](https://img.shields.io/badge/ci-passing-green)](https://ci.example.com)\n")
        self.assertEqual(f["images"][0]["src"], "https://img.shields.io/badge/ci-passing-green")
        self.assertEqual(targets(f), ["https://ci.example.com"])
        self.assertEqual(len(f["badges"]), 1)

    def test_comments_hide_fake_links(self):
        f = facts("Text <!-- [x](inline.md) --> more.\n\n<!--\n[y](block.md)\n<a href=\"z.md\">z</a>\n"
                  "<img src=\"q.png\">\n-->\n\nEnd.\n")
        self.assertEqual(f["links"], [])
        self.assertEqual(f["images"], [])
        self.assertEqual([c["line"] for c in f["comments"]], [1, 3])

    def test_inline_code_hides_links(self):
        f = facts("Write `[x](y.md)` or ``a ` [z](w.md)`` to link.\n")
        self.assertEqual(f["links"], [])

    def test_escaped_brackets_are_not_links(self):
        self.assertEqual(facts("\\[not](a.md)\n")["links"], [])

    def test_destinations_decode_escapes_and_entities(self):
        f = facts("[g](guide\\(v2\\).md) [x](A&amp;B.md) [p](<a\\>b.md>) [n](a\\nb.md) [r][r] "
                  "![i](shot\\_1.png) <a href=\"c&amp;d.md\">h</a> [q](&#x41;&bogus;.md)\n\n"
                  "[r]: R&amp;D\\!.md\n")
        self.assertEqual(targets(f), ["guide(v2).md", "A&B.md", "a>b.md", "a\\nb.md", "R&D!.md", "A&bogus;.md",
                                      "c&d.md"])
        self.assertEqual([i["src"] for i in f["images"]], ["shot_1.png"])

    def test_escaped_backtick_before_a_run(self):
        for text in ("Ends in \\``\n", "a \\`` b `` c\n", "\\```x``\n"):
            with self.subTest(text=text):
                facts(text)
        # The escaped tick is text; the ticks after it open a code span only if a run as long closes it.
        self.assertEqual(targets(facts("a \\```[x](y.md)``\n")), [])
        self.assertEqual(targets(facts("a \\``[x](y.md)``\n")), ["y.md"])

    def test_footnotes_are_not_links(self):
        self.assertEqual(facts("Text[^1].\n\n[^1]: A note.\n")["links"], [])

    def test_first_image_line(self):
        self.assertEqual(facts("a\n\nb ![x](y.png)\n")["first_image_line"], 3)


class Counts(unittest.TestCase):
    def test_words_skip_code_urls_images_comments_and_separators(self):
        f = facts("# Hello world\n\nIt's a well-known [link text](http://example.com/very/long/path) "
                  "![alt words](img.png) <!-- hidden words -->\n\n```\nnot counted here\n```\n\n"
                  "| A | B |\n| --- | --- |\n| c | `d` |\n\nhttps://bare.example.com/x\n")
        # Hello world It's a well-known link text A B c d
        self.assertEqual(f["words"], 11)

    def test_html_entities_are_not_words(self):
        self.assertEqual(facts("&nbsp;one&nbsp;two &amp; three\n")["words"], 3)

    def test_badges_need_the_badge_pattern(self):
        f = facts("![a](https://img.shields.io/x) ![b](screenshots/hero.png) "
                  "![c](https://github.com/o/r/actions/workflows/ci.yml/badge.svg)\n")
        self.assertEqual([b["src"][:20] for b in f["badges"]], ["https://img.shields.", "https://github.com/o"])

    def test_install_line(self):
        self.assertEqual(facts("# X\n\n## Uninstall\n\n## Installation\n")["install_line"], 5)
        self.assertEqual(facts("# X\n\n## Quick start\n")["install_line"], 3)
        self.assertIsNone(facts("# X\n\n## Usage\n")["install_line"])

    def test_toc_from_anchor_list(self):
        toc = "# X\n\n- [A](#a)\n- [B](#b)\n- [C](#c)\n- [D](#d)\n\n## A\n"
        self.assertTrue(facts(toc)["toc"])
        self.assertFalse(facts(toc.replace("- [D](#d)\n", ""))["toc"])

    def test_toc_from_heading(self):
        self.assertTrue(facts("# X\n\n## Table of Contents\n\nStuff\n")["toc"])

    def test_tables(self):
        f = facts("| Name | Does |\n| --- | --- |\n| `a\\|b` | one |\n| c | two |\n\nAfter\n")
        self.assertEqual(f["tables"][0]["header"], ["Name", "Does"])
        self.assertEqual([r["cells"][0] for r in f["tables"][0]["rows"]], ["`a\\|b`", "c"])

    def test_markers(self):
        f = facts("<!-- matches: examples/out.txt#L2-L4 -->\n```text\nx\n```\n\n"
                  "<!-- matches: a.txt -->\n~~~\ny\n~~~\n\n<!-- matches: b.txt -->\n\n```\nz\n```\n")
        self.assertEqual([(m["line"], m["path"], m["start"], m["end"]) for m in f["markers"]],
                         [(1, "examples/out.txt", 2, 4), (6, "a.txt", None, None)])

    def test_marker_line_numbers_of_any_size(self):
        f = facts("<!-- matches: a.txt#L" + "9" * 5000 + " -->\n```\nx\n```\n\n"
                  "<!-- matches: b.txt#L2-L99999999999999999999 -->\n```\ny\n```\n")
        self.assertEqual([(m["path"], m["start"] > 10 ** 6, m["end"] > 10 ** 6) for m in f["markers"]],
                         [("a.txt", True, True), ("b.txt", False, True)])

    def test_front_matter_is_skipped(self):
        f = facts("---\ntitle: x\n---\n# Real\n")
        self.assertEqual([h["text"] for h in f["headings"]], ["Real"])


class Cost(unittest.TestCase):
    """Hostile pages of a few hundred KB are read in well under a second each."""

    def assert_fast(self, text):
        started = time.monotonic()
        result = facts(text)
        self.assertLess(time.monotonic() - started, 1.0)
        return result

    def test_nested_brackets(self):
        self.assert_fast("[" * 100000 + "]" * 100000 + "(x)\n")
        self.assert_fast("![" * 50000 + "]" * 50000 + "[r]\n\n[r]: x\n")

    def test_heading_with_many_backtick_runs(self):
        f = self.assert_fast("# " + "".join("`" * k + "a" for k in range(1, 700)) + "\n")
        self.assertEqual(len(f["headings"]), 1)

    def test_spaces_inside_a_link_destination(self):
        self.assert_fast("[a](x" + " " * 200000 + "y)\n")

    def test_deep_block_quotes(self):
        f = self.assert_fast("> " * 50000 + "```\n" + ("> " * 50000 + "x\n") * 3)
        self.assertEqual(len(f["fences"]), 1)

    def test_emphasis_runs(self):
        self.assert_fast("# " + "_a" * 100000 + "\n")
        self.assert_fast("# " + "*a " * 50000 + "a*" * 50000 + "\n")


if __name__ == "__main__":
    unittest.main()
