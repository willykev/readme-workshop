# The conversation

Contents: [How to ask](#how-to-ask) · [Stop 1](#stop-1-the-reader-and-the-job) ·
[Stop 2](#stop-2-what-to-highlight) · [Stop 3](#stop-3-the-plan) ·
[Stop 4](#stop-4-the-exact-draft) · [Replies](#replies) ·
[Preservation map](#preservation-map) · [Later runs](#later-runs) ·
[Review mode](#review-mode)

The examples below use a made-up project, `cookconv`, a command-line tool
and Python library that scales recipes and converts their units.

## How to ask

- Lead with the proposal, then the question. The person should be able to
  answer "ok".
- At most three numbered questions per stop. Each says what you will
  assume if the person does not know: "If you're not sure, I'll lead with
  pipx."
- Say which stop this is ("stop 2 of 4") so the person knows how far along
  they are.
- Keep each stop under about 30 lines. Put evidence in short form
  (`cli.py:40`), not quoted code.
- End the turn after asking. Do not carry on drafting in the same message.
- A host's question tool may present a choice of up to four options (the
  pitch at stop 3). Keep the full stop text in the message anyway, so the
  choice makes sense on its own and survives in a transcript.

## Stop 1: the reader and the job

```markdown
**What I found** (stop 1 of 4)

cookconv scales recipes and converts their units, as a command-line tool and a Python library.

- **For:** people who keep recipes as text files (they run it), and Python developers (they import it).
- **Install:** `pipx install cookconv` (pyproject.toml:12 declares the `cookconv` command).
- **First result:** `cookconv scale pancakes.txt --serves 6` prints the recipe for six (examples/pancakes.txt; tests/test_cli.py:40).
- **Runs on:** Python 3.10 or later, any system (pyproject.toml:8).
- **Your files:** reads the file you name; writes only with `-o` (cli.py:88).
- **Couldn't tell:** whether it is on PyPI (no release workflow), and which reader comes first.

Is this right? Correct anything that isn't, and:
1. Is it published on PyPI? If not, I'll show install from source.
2. Who should the page speak to first, cooks or developers? I'd lead with cooks.
```

## Stop 2: what to highlight

```markdown
**What to highlight** (stop 2 of 4)

Ranked by what a new user runs into first and needs to decide; ★ = recommended for the feature list.

★ 1. **Scale to any serving count.** `--serves 6` rescales every quantity. cli.py:40, 12 tests. Score 6.
★ 2. **Metric or US units.** `--to metric` converts cups, ounces and °F. convert.py:15. Score 6.
★ 3. **Reads plain text.** One ingredient per line, no special format. parse.py:22, examples/. Score 5.
★ 4. **Rounds to kitchen sizes.** 0.33 cup becomes ⅓ cup. round.py:9. Score 4.
★ 5. **Use it from Python.** `scale(recipe, serves=6)`. __init__.py:3 exports it. Score 4.
  6. JSON output with `--json`. cli.py:61. Score 3.
  7. Shopping list across recipes. cli.py:120, untested. Score 2.

Guessed: "Works with exports from recipe apps": guessed from a parser named `import_csv`; confirm or drop.
Left out: `--debug-tokens` (developer flag), `_legacy_parse` (internal).

Are these the ones to highlight? Reorder, drop or add.
```

## Stop 3: the plan

```markdown
**The plan** (stop 3 of 4)

Pitch:
- A (recommended): cookconv scales recipes and converts their units, from the command line or from Python.
- B: Resize any recipe for any number of people, in metric or US units.
- C: A recipe scaler and unit converter for plain-text recipes.

Sections: name and pitch · links · a real run (input and output) · features (5) · install · your first recipe · from Python · your files · more.

Proof: I'll run `cookconv scale examples/pancakes.txt --serves 6` in a scratch copy and show the real output, and run the Python example the same way. Nothing in your project changes until you approve the draft.

Which pitch, and shall I go ahead?
```

Say plainly at stop 3 if the proof needs something the project lacks: a
sample file, a `--screenshot` option, a script that draws the pictures, a
fixed clock. Propose adding it as part of the change set.

## Stop 4: the exact draft

Show, in this order:

1. The whole page in a fenced block (or, for an existing README, the full
   new page and then a short list of what changed).
2. Every file that will be added or changed, with one line each: `README.md
   (new, 142 lines)`, `examples/pancakes-6.txt (new, the output shown)`.
3. The checker's result: `0 errors, 2 warnings (RW104 line 31: "simple"
   with no number; RW113 line 90)`, and what you did about each.
4. Claims you could not verify, each with what would settle it.
5. For an existing README, the [Preservation map](#preservation-map).

Ask: **"Write these files?"** Write only after a clear yes to this stop.

## Replies

| The person says | Do |
|---|---|
| "ok", "yes", "good", "go ahead" | Accept this stop and move on |
| A correction ("it's for developers") | Change the proposal; show the changed part; ask again |
| A reorder or a drop ("swap 2 and 4, drop 5") | Apply it; show the new list; ask again |
| Part approval ("yes, but no performance section") | Apply the change; at stop 4, show the changed draft and ask again |
| "No" with no detail | Ask what to change; offer the two most likely changes |
| Nothing, or something unrelated | Do not take it as approval. Repeat the open question in one line |
| "Just write it" | Go to stop 4 with your assumptions listed as a numbered list; still ask before writing |
| "Stop", "cancel" | End; nothing written; say what was not done |

A yes to stop 4 approves exactly the files listed. If the person asks for
a change after seeing the draft, make it and show stop 4 again. If any
target file changed on disk since the draft (re-read it just before
writing), show what changed and ask again.

## Preservation map

An existing README often holds things that must survive a rewrite. Before
stop 4, list every block of the old page and decide:

| Old block | Decision | Where it goes |
|---|---|---|
| License and copyright notice | Keep | Bottom, one line and a link |
| Funding or sponsor acknowledgment | Keep, ask before moving | Bottom, or where the owner wants it |
| Links to translations | Keep | One line under the link row |
| Security contact, code of conduct | Keep or move | `SECURITY.md` / bottom links |
| Citation (BibTeX, DOI) | Keep | Its own short section near the end |
| Build instructions | Move | `CONTRIBUTING.md` (one link stays) |
| Full option tables, every command | Move | `docs/guide.md` |
| Roadmap, plans, history of the project | Cut, ask first | Nowhere (or an issue) |
| Badge row of eight | Cut to two that a user acts on | Under the pitch or at the bottom |

Never drop a license, funding, security, citation or legal notice
without the person saying so explicitly. Show the map at stop 4.

## Later runs

When a README already exists and was written this way:

1. Find the commit that last changed it: `discover.py` reports
   `history.last_readme_commit`.
2. Run `discover.py --root DIR --since THAT_COMMIT` and read what changed:
   new or removed commands, options, exports, tools, inputs; renamed files;
   a new install channel; changelog entries since then. It lists committed
   changes and untracked files only; if the person has uncommitted edits,
   read those working files too.
3. Check the current page with `check_readme.py`: broken links and
   parity errors show what drifted.
4. Propose only the changes, as a short stop 2 (new candidates, removals)
   and a stop 4 diff. Leave the rest of the page as it is.

## Review mode

Edit nothing. Report, in this order:

1. **The four questions**: for each, can a stranger answer it from the
   first screen (about 25 lines on GitHub), and where.
2. **The checker's findings** (`check_readme.py --format text`), errors
   first.
3. **Claims that do not match the code**, each with the line in the README
   and the evidence (path:line).
4. **What is missing** that the decision card says a reader needs.
5. **The three changes with the most effect**, each with the exact new
   text where it is short.

Offer to make the changes; if the person agrees, continue at stop 3.
