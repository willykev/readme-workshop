# Tally

Tally counts the words in Markdown files and prints a table, one row for each
file. It reads only the files you name, never writes to them, and needs no
network connection.

[Install](#install) · [Guide](docs/guide.md#first-steps) · [Changelog][changes]

![A terminal running tally on two notes, with a table of their word counts under the command](screenshots/hero.png)

## Install

Tally needs Python 3.11 or newer.

```sh
pip install tally-words
```

## Count a folder

Give it files or folders, and it prints one row for each Markdown file it
finds:

<!-- matches: examples/out.txt -->
```text
notes/a.md      120
notes/b.md       80
```

The second row on its own:

<!-- matches: examples/out.txt#L2-L2 -->
~~~text
notes/b.md       80
~~~

1. Pick a folder.

   ```sh
   tally notes/
   ```

2. Read the table, which ends with a total.

### Options

| Option | What it does |
| --- | --- |
| `--json` | Prints JSON instead of a table |
| `--total` | Adds a total row at the end |

See <https://example.com/tally> or the [list of options](docs/guide.md#options-and-flags).
Read <a href="docs/guide.md#your-data">where tally keeps nothing</a>, and
report a problem in [the issues](../../issues).

## More

The [guide](docs/guide.md) covers every option, and [the changelog][changes]
says what is new. <!-- an aside with a [fake link](nowhere.md) -->

[changes]: CHANGELOG.md
