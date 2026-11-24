import os
import sys
import tempfile
import textwrap
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "skills", "readme-workshop", "scripts"))

import formats  # noqa: E402


def yaml(text):
    return formats.read_yaml(textwrap.dedent(text).lstrip("\n"))


class TempFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def file(self, name, data):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path


class TomlTests(TempFiles):
    def test_reads_a_table(self):
        path = self.file("pyproject.toml", '[project]\nname = "x"\nversion = "1.0"\n[project.scripts]\nx = "x:main"\n')
        self.assertEqual(formats.read_toml(path)["project"]["scripts"], {"x": "x:main"})

    def test_invalid_or_missing_is_none(self):
        self.assertIsNone(formats.read_toml(self.file("bad.toml", "[project\nname =")))
        self.assertIsNone(formats.read_toml(os.path.join(self.tmp.name, "missing.toml")))
        self.assertIsNone(formats.read_toml(self.file("latin.toml", b"name = \"\xff\"\n")))

    def test_parse_toml_text(self):
        self.assertEqual(formats.parse_toml('a = 1'), {"a": 1})
        self.assertIsNone(formats.parse_toml("a = "))


class JsonTests(TempFiles):
    def test_bom_is_tolerated(self):
        path = self.file("package.json", b"\xef\xbb\xbf" + b'{"name": "x", "bin": {"x": "cli.js"}}')
        self.assertEqual(formats.read_json(path), {"name": "x", "bin": {"x": "cli.js"}})

    def test_list_is_returned(self):
        self.assertEqual(formats.read_json(self.file("a.json", "[1, 2]")), [1, 2])

    def test_errors_and_scalars_are_none(self):
        self.assertIsNone(formats.read_json(self.file("bad.json", "{name: x}")))
        self.assertIsNone(formats.read_json(self.file("scalar.json", "3")))
        self.assertIsNone(formats.read_json(os.path.join(self.tmp.name, "missing.json")))
        self.assertIsNone(formats.read_json(self.file("bytes.json", b"\xff\xfe{")))


class YamlTests(unittest.TestCase):
    def test_action_file(self):
        value, certain = yaml("""
            name: 'Hello'
            description: "Greets \\"you\\"\\tnow"
            inputs:
              who-to-greet:  # a comment
                description: Who to greet
                required: true
                default: World
            outputs:
              time:
                description: The time
            runs:
              using: node20
              main: dist/index.js
            branding: {icon: 'mic', color: blue}
        """)
        self.assertTrue(certain)
        self.assertEqual(value["description"], 'Greets "you"\tnow')
        self.assertEqual(value["inputs"]["who-to-greet"], {"description": "Who to greet", "required": True, "default": "World"})
        self.assertEqual(value["runs"]["using"], "node20")
        self.assertEqual(value["branding"], {"icon": "mic", "color": "blue"})

    def test_compose_file(self):
        value, certain = yaml("""
            services:
              web:
                build: .
                ports:
                  - "5000:5000"
                  - 8080:80
                environment:
                  - FLASK_ENV=development
                command: ["python", "app.py"]
              db:
                image: postgres:16
        """)
        self.assertTrue(certain)
        self.assertEqual(value["services"]["web"]["ports"], ["5000:5000", "8080:80"])
        self.assertEqual(value["services"]["web"]["command"], ["python", "app.py"])
        self.assertEqual(value["services"]["db"], {"image": "postgres:16"})

    def test_sequence_of_mappings(self):
        value, certain = yaml("""
            - id: black
              name: black
              types_or: [python, pyi]
            - id: two
              args:
              - --x
              - --y
            - - nested
              - list
        """)
        self.assertTrue(certain)
        self.assertEqual(value[0], {"id": "black", "name": "black", "types_or": ["python", "pyi"]})
        self.assertEqual(value[1]["args"], ["--x", "--y"])
        self.assertEqual(value[2], ["nested", "list"])

    def test_scalar_types(self):
        value, certain = yaml("""
            t: true
            f: False
            n: null
            tilde: ~
            empty:
            i: 42
            neg: -7
            hex: 0x1F
            fl: 1.5
            exp: 1e3
            ver: 1.2.3
            quoted: "true"
            single: 'it''s'
            url: http://example.com:80/x#frag
            apostrophe: don't # comment
        """)
        self.assertTrue(certain)
        self.assertEqual(value, {"t": True, "f": False, "n": None, "tilde": None, "empty": None, "i": 42, "neg": -7,
                                 "hex": 31, "fl": 1.5, "exp": 1000.0, "ver": "1.2.3", "quoted": "true", "single": "it's",
                                 "url": "http://example.com:80/x#frag", "apostrophe": "don't"})

    def test_block_scalars(self):
        value, certain = yaml("""
            literal: |
              line one
                indented
              line three
            strip: |-
              no newline
            keep: |+
              kept

            folded: >
              folded text
              continues here

              new paragraph
            folded_strip: >-
              a
              b
            last: x
        """)
        self.assertTrue(certain)
        self.assertEqual(value["literal"], "line one\n  indented\nline three\n")
        self.assertEqual(value["strip"], "no newline")
        self.assertEqual(value["keep"], "kept\n\n")
        self.assertEqual(value["folded"], "folded text continues here\nnew paragraph\n")
        self.assertEqual(value["folded_strip"], "a b")
        self.assertEqual(value["last"], "x")

    def test_block_scalar_in_a_sequence(self):
        value, certain = yaml("""
            steps:
              - uses: actions/checkout@v4
              - run: |
                  echo hi
                  echo there
                shell: bash
        """)
        self.assertTrue(certain)
        self.assertEqual(value["steps"][1], {"run": "echo hi\necho there\n", "shell": "bash"})

    def test_flow_collections(self):
        value, certain = yaml("""
            a: [1, two, "three, four", [5, 6]]
            b: {x: 1, 'y': [a, b], z: {deep: true}}
            c: []
            d: {}
        """)
        self.assertTrue(certain)
        self.assertEqual(value["a"], [1, "two", "three, four", [5, 6]])
        self.assertEqual(value["b"], {"x": 1, "y": ["a", "b"], "z": {"deep": True}})
        self.assertEqual((value["c"], value["d"]), ([], {}))

    def test_flow_over_several_lines(self):
        value, certain = yaml("""
            on: [push,
                 pull_request]
            next: 1
        """)
        self.assertEqual(value, {"on": ["push", "pull_request"], "next": 1})
        self.assertTrue(certain)

    def test_multiline_plain_and_quoted(self):
        value, certain = yaml("""
            description: This is a long
              description that wraps
            quoted: "first
              second"
            after: 1
        """)
        self.assertTrue(certain)
        self.assertEqual(value["description"], "This is a long description that wraps")
        self.assertEqual(value["quoted"], "first second")
        self.assertEqual(value["after"], 1)

    def test_comments_and_document_markers(self):
        value, certain = yaml("""
            # leading comment
            ---
            a: 1  # trailing
            # between
            b: "# not a comment"
            ...
        """)
        self.assertTrue(certain)
        self.assertEqual(value, {"a": 1, "b": "# not a comment"})

    def test_crlf_and_bom(self):
        value, certain = formats.read_yaml("\ufeffa: 1\r\nb:\r\n  - x\r\n")
        self.assertEqual((value, certain), ({"a": 1, "b": ["x"]}, True))

    def test_empty_and_scalar_documents(self):
        self.assertEqual(formats.read_yaml(""), (None, True))
        self.assertEqual(formats.read_yaml("# only a comment\n"), (None, True))
        self.assertEqual(formats.read_yaml("just text"), ("just text", True))

    def test_anchors_and_aliases_are_uncertain(self):
        value, certain = yaml("""
            base: &base
              x: 1
            copy: *base
        """)
        self.assertFalse(certain)
        self.assertEqual(value["base"], {"x": 1})
        self.assertIn("copy", value)

    def test_merge_key_is_uncertain(self):
        value, certain = yaml("""
            base: &b {x: 1}
            item:
              <<: *b
              y: 2
        """)
        self.assertFalse(certain)
        self.assertEqual(value["item"]["y"], 2)

    def test_tags_are_uncertain(self):
        value, certain = yaml("""
            when: !!str 2024-01-01
            custom: !Ref Thing
        """)
        self.assertFalse(certain)
        self.assertEqual(value["when"], "2024-01-01")

    def test_multiple_documents_are_uncertain(self):
        value, certain = yaml("""
            a: 1
            ---
            b: 2
        """)
        self.assertFalse(certain)
        self.assertEqual(value, {"a": 1})

    def test_document_after_an_end_marker_is_uncertain(self):
        self.assertEqual(formats.read_yaml("a: 1\n...\n---\nb: 2\n"), ({"a": 1}, False))
        self.assertEqual(formats.read_yaml("a: 1\n...\n# only a comment\n"), ({"a": 1}, True))

    def test_complex_keys_are_uncertain(self):
        value, certain = yaml("""
            ? complex key
            : value
            plain: 1
        """)
        self.assertFalse(certain)
        self.assertEqual(value["plain"], 1)

    def test_colon_in_plain_value_is_uncertain(self):
        value, certain = yaml("description: Use when: writing\n")
        self.assertFalse(certain)
        self.assertEqual(value, {"description": "Use when: writing"})

    def test_tab_indentation_is_uncertain(self):
        _, certain = formats.read_yaml("a:\n\tb: 1\n")
        self.assertFalse(certain)

    def test_unclosed_quote_or_flow_is_uncertain(self):
        self.assertFalse(formats.read_yaml('a: "open\n')[1])
        value, certain = formats.read_yaml("a: [1, 2\n")
        self.assertFalse(certain)

    def test_bad_indentation_is_uncertain(self):
        value, certain = yaml("""
            a: 1
              b: 2
            c: 3
        """)
        self.assertFalse(certain)
        self.assertEqual(value["c"], 3)

    def test_quoted_scalar_line_breaks(self):
        value, certain = yaml(r"""
            joined: "one\
              two"
            literal: "back\\
              slash"
            blank: 'a

              b'
            pair: 'it''s
              here'
            after: 1
        """)
        self.assertTrue(certain)
        self.assertEqual(value, {"joined": "onetwo", "literal": "back\\ slash", "blank": "a\nb", "pair": "it's here",
                                 "after": 1})

    def test_flow_with_brackets_in_strings_over_several_lines(self):
        value, certain = yaml("""
            a: ["x]", 'y,
              z]', it's, {k: "v}"},
              w]
            b: {p: [1,
              2], q: '}'}
            next: 1
        """)
        self.assertTrue(certain)
        self.assertEqual(value, {"a": ["x]", "y, z]", "it's", {"k": "v}"}, "w"], "b": {"p": [1, 2], "q": "}"}, "next": 1})


    def test_hash_inside_a_quoted_value_that_continues_over_lines(self):
        value, certain = formats.read_yaml('a: ["x\n  # y", z]\nb: {k: \'p\n  # q\', m: 1}\nc: 1\n')
        self.assertEqual((value, certain), ({"a": ["x # y", "z"], "b": {"k": "p # q", "m": 1}, "c": 1}, True))
        value, certain = formats.read_yaml('a: ["x\n  # y" ]  # a comment\nb: 2\n')
        self.assertEqual((value, certain), ({"a": ["x # y"], "b": 2}, True))

    def test_chomping_counts_the_line_breaks_the_text_has(self):
        cases = {"a: |+\n  kept\n": "kept\n", "a: |+\n  kept": "kept", "a: |\n  kept": "kept",
                 "a: |\n  kept\n": "kept\n", "a: |+\n  kept\n\n": "kept\n\n", "a: >+\n  kept\n": "kept\n",
                 "a: |+\n  kept\n  \n": "kept\n\n", "a: |+\n\n": "\n", "a: |-\n  kept\n": "kept",
                 "a: |+\n  kept\nb: 1\n": "kept\n", "a: |+\n  kept\n\nb: 1": "kept\n\n",
                 "a: |\n  one\n  two": "one\ntwo", "a: >\n  one\n  two\n": "one two\n", "a: |\n\n": ""}
        for text, want in cases.items():
            with self.subTest(text=text):
                value, certain = formats.read_yaml(text)
                self.assertTrue(certain)
                self.assertEqual(value["a"], want)


class YamlCostTests(unittest.TestCase):
    """Hostile files the scanner reads (up to 256 KB) take time in proportion to their size."""

    def read_fast(self, text):
        self.assertGreaterEqual(len(text), 256 * 1024)
        started = time.monotonic()
        result = formats.read_yaml(text)
        self.assertLess(time.monotonic() - started, 1.0)
        return result

    def test_unclosed_flow_collection(self):
        for opener in ("[", "{"):
            with self.subTest(opener=opener):
                value, certain = self.read_fast("a: %s\n" % opener + "".join("x%d,\n" % n for n in range(40000)))
                self.assertFalse(certain)
                self.assertEqual(len(value["a"]), 40000)

    def test_unclosed_quoted_scalar(self):
        for quote in "\"'":
            with self.subTest(quote=quote):
                value, certain = self.read_fast("a: %sstart\n" % quote + "x\n" * (128 * 1024 + 1))
                self.assertFalse(certain)
                self.assertTrue(value["a"].startswith("start x x"))

    def test_long_closed_values_still_parse(self):
        value, certain = self.read_fast("a: [\n" + "x,\n" * (128 * 1024) + "]\nb: \"\n" + "y\n" * 1000 + "\"\nc: 1\n")
        self.assertTrue(certain)
        self.assertEqual((len(value["a"]), value["b"][:4], value["c"]), (128 * 1024, " y y", 1))


class FrontmatterTests(unittest.TestCase):
    def test_splits_frontmatter(self):
        data, body, certain = formats.frontmatter("---\nname: x\ndescription: Does a thing\n---\n# Body\n\ntext\n")
        self.assertEqual(data, {"name": "x", "description": "Does a thing"})
        self.assertEqual(body, "# Body\n\ntext\n")
        self.assertTrue(certain)

    def test_no_frontmatter(self):
        self.assertEqual(formats.frontmatter("# Title\n---\n"), (None, "# Title\n---\n", True))

    def test_unclosed_frontmatter(self):
        data, body, certain = formats.frontmatter("---\nname: x\n")
        self.assertIsNone(data)
        self.assertEqual(body, "---\nname: x\n")
        self.assertFalse(certain)

    def test_empty_frontmatter(self):
        self.assertEqual(formats.frontmatter("---\n---\nbody"), ({}, "body", True))

    def test_non_mapping_frontmatter(self):
        data, body, certain = formats.frontmatter("---\n- a\n- b\n---\nbody\n")
        self.assertIsNone(data)
        self.assertEqual(body, "body\n")
        self.assertFalse(certain)

    def test_crlf_bom_and_dots(self):
        data, body, certain = formats.frontmatter("\ufeff---\r\nname: x\r\n...\r\nbody\r\n")
        self.assertEqual((data, body, certain), ({"name": "x"}, "body\r\n", True))

    def test_uncertain_frontmatter_keeps_values(self):
        data, _, certain = formats.frontmatter("---\nname: x\ndescription: Triggers: a, b\n---\n")
        self.assertEqual(data["name"], "x")
        self.assertFalse(certain)


if __name__ == "__main__":
    unittest.main()
