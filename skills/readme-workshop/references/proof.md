# Showing it working, without inventing anything

Contents: [The rule](#the-rule) · [Proof by kind](#proof-by-kind) ·
[Making a real run safe](#making-a-real-run-safe) · [Keeping it true](#keeping-it-true) ·
[When it cannot be run](#when-it-cannot-be-run)

## The rule

"Show it working" means an input, the supported way in, and a result the
reader can recognize, produced by a real run. Everything shown on the page
came out of the project: no hand-written output, no mocked screenshot, no
"example output" typed from memory, no number nobody measured.

## Proof by kind

| Kind | Proof | Kept true by |
|---|---|---|
| App | A loop or still drawn by the app from sample content | A script in the project that redraws every picture (`bin/screenshots`) |
| Terminal | A command and its real output, as text | An example marker comparing the block with a saved output file |
| Service | The start command and the first request with its real response, or the first screen from seeded data | A saved response file and a marker; the compose file for ports and paths |
| Library | The smallest program and its real output | The project's example file, run by its tests, and a marker |
| Extension | A real exchange in the host, a tool table, or a picture in the host | Names checked against `SKILL.md`, manifests and registrations |
| Automation | The pinned snippet and what a real run reports | Inputs and outputs checked against `action.yml`; a link to a real run |

## Making a real run safe

Ask at stop 3 before running anything, and say what you will run. Then:

- Work in a scratch copy of the project outside it, never in the project
  itself: builds, tests and interpreters leave files behind (build folders,
  `node_modules`, `__pycache__`). Copy the working files, which are what you
  read, without `.git` (`tar -C PROJECT_DIR --exclude=.git -cf - . | tar -C
  DIR -xf -`); not `git worktree add`, which runs the project's git hooks,
  and not `git archive`, which leaves out uncommitted work. Set
  `PYTHONDONTWRITEBYTECODE=1` for Python and build out of tree.
- Know what the copy does and does not do. It keeps the project clean; it
  does not stop the code from reading your files, using the network or
  seeing your environment variables. Run a project you do not trust only in
  a container or VM with no network and no credentials, with environment
  variables cleared (`env -i PATH="$PATH" HOME=DIR …`), or give the person
  the command to run themselves.
- Point the program's home and data folders at the scratch folder
  (`HOME`, `XDG_*`, an app's `--data-dir`), so nothing personal can appear
  in the output and the owner's own data is not changed. This is for clean
  output, not isolation.
- Cut it off from what it should not reach: no real accounts, no real
  tokens, no network unless the run needs it. Use the project's own
  sample data or make a small, believable sample (a weekend trip, a week of
  errands, a short essay), never real names or files.
- Fix the clock where output shows dates (an option, `faketime`, or a
  sample with absolute dates).
- Keep the output as it came. Trim long output with a visible `…` line;
  never edit values.

Files the proof needs inside the project (sample input, saved output, a
capture script) are part of the change set shown at stop 4. They are not
written before then.

## Keeping it true

An example marker ties a code block on the page to a file in the
project:

````markdown
<!-- matches: examples/pancakes-6.txt -->
```text
Pancakes (serves 6)
```
````

`check_readme.py` fails (RW007) when the block and the file differ, so a
later change to the tool shows up as a failing check instead of a page that
lies. A line range is allowed: `<!-- matches: examples/demo.py#L3-L12 -->`.

Pictures stay true the same way: a script in the project redraws them from
the sample, and a release redraws them when the interface changes.

## When it cannot be run

The program needs hardware, an account, a paid API, a GPU, a platform you
are not on, or the owner declined at stop 3. Then:

- Say so at stop 3 and offer the options: the owner runs a command you
  give them and pastes the output; you add a capture script for them to
  run; or the page shows the input and describes the result in words,
  marked as not shown.
- Never fill the gap with a plausible fake. A missing picture costs less
  than a false one.
- At stop 4, list every proof that was not produced by a real run.
