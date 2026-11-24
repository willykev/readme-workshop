# readme-workshop guide

readme-workshop is a skill that helps an agent write, review and update a
project's README together with its owner. This guide covers everything it
does. For a quick start, see the [README](../README.md).

**Contents:** [Install](#install) · [Write a README](#write-a-readme) ·
[Improve an existing README](#improve-an-existing-readme) ·
[Review a README](#review-a-readme) · [Update after changes](#update-after-changes) ·
[Pictures and examples](#pictures-and-examples) · [Write the user guide](#write-the-user-guide) ·
[Work without questions](#work-without-questions) · [discover.py](#discoverpy) ·
[check_readme.py](#check_readmepy) · [The GitHub Action](#the-github-action) ·
[What it reads and changes](#what-it-reads-and-changes) · [Troubleshooting](#troubleshooting) ·
[What it does not do](#what-it-does-not-do)

## Install

The skill is one folder, `skills/readme-workshop/`. Each agent below can
install it as a plugin, which also keeps it up to date.

### Claude Code

```sh
claude plugin marketplace add willykev/readme-workshop
claude plugin install readme-workshop@readme-workshop
```

Start a new session; `/plugin` lists it as installed.

### Codex

```sh
codex plugin marketplace add willykev/readme-workshop
codex plugin add readme-workshop@readme-workshop
```

### Grok

```sh
grok plugin install willykev/readme-workshop --trust
```

### Antigravity

```sh
agy plugin install https://github.com/willykev/readme-workshop
```

### Any agent that reads Agent Skills

With the GitHub CLI, for any of the agents it supports:

```sh
gh skill install willykev/readme-workshop readme-workshop --agent claude-code
```

Or copy `skills/readme-workshop/` into the agent's skills folder (for
example `~/.agents/skills/` or `~/.claude/skills/`).

### Requirements

An agent that can read files and run shell commands. The two scripts need
Python 3.11 or later and nothing else; without Python the skill still
works, following the same steps by hand.

### Update and remove

Plugins update with the host's own command (`claude plugin update
readme-workshop`, `codex plugin marketplace upgrade`, `grok plugin update`,
reinstall for Antigravity). Remove with `claude plugin uninstall
readme-workshop`, `codex plugin remove readme-workshop@readme-workshop`, `grok plugin
uninstall readme-workshop` or `agy plugin uninstall readme-workshop`, or
delete the copied folder. It keeps nothing outside its own folder.

## Write a README

Ask in your own words: "Write a README for this project." The agent loads
the skill, reads the project, and then stops four times for you to agree:

1. **The reader and the job.** What the project is, who it is for, how it
   is installed, the first useful result, and what it could not find out.
   Correct anything wrong; answer the questions it asks.
2. **What to highlight.** Eight to twelve candidate features with their
   evidence and score, the four to seven it recommends, its guesses listed
   apart. Reorder, drop or add.
3. **The plan.** Three pitches to choose from, the sections in order, and
   how it will show the project working. Nothing runs before you agree.
4. **The exact draft.** The whole page, every file it would add or change,
   the checker's result and any claim it could not verify. It writes only
   after you say yes.

"ok" accepts a stop. Silence never does, and neither does a yes to an
earlier stop. "Just write it" goes straight to stop 4 with the assumptions
listed; it still asks before writing. "Stop" ends it with nothing written.

## Improve an existing README

Ask to improve or rewrite it. The stops are the same; at stop 4 the agent
also shows a Preservation Map: every block of the old page with keep, move
or cut, and where it goes. License, funding, security, citation and legal
notices are never dropped unless you say so.

## Review a README

Ask for a review or an audit. The agent edits nothing. It reports whether a
stranger can answer the four questions from the first screen, the checker's
findings, claims that do not match the code (with the evidence), what a
reader needs that is missing, and the three changes with the most effect.

## Update after changes

Ask to update the README after a release or a change. The agent finds the
commit that last changed the README, reads what changed since then (new or
removed commands, options, exports, tools, inputs; renamed files; changelog
entries), checks the current page for drift, and proposes only the changes.

## Pictures and examples

Ask for screenshots, a demo or examples. The agent proposes what to show and
how to make it at stop 3, makes it from sample content in a scratch folder,
and adds a script to the project that redraws it, so the pictures stay true
when the interface changes. It never invents output, a screenshot or a
number. If something cannot be run where the agent is, it says so and
leaves a marked gap.

## Write the user guide

Ask for `docs/guide.md`. The same stops apply. The guide is organized by
task and holds what the README samples: every command, key, option, input
and setting, where data lives, troubleshooting and limits.

## Work without questions

Say so in the request ("don't ask me anything"), or set
`README_WORKSHOP_NONINTERACTIVE=1` for unattended runs. The agent takes its
own recommendation at each stop and replies with the findings, the
highlights, the draft and its open questions. It writes files only when the
request explicitly asked for them to be written without review, and even
then it never replaces an existing README: it writes `README.draft.md`
beside it.

## discover.py

```sh
python3 -I -B skills/readme-workshop/scripts/discover.py --root DIR [--since REF] [--format json|text]
```

Reads a project and reports, with path and line for every fact: kinds
(app, terminal, service, library, extension, automation, with sub-kinds),
manifests, entry points, surfaces (commands and options, public API, MCP
tools, slash commands, skills, hooks, Action inputs and outputs, routes,
environment variables, shortcuts, config files), install channels,
platforms, network, storage and telemetry signals, docs, pictures,
examples, tests, project rules and git history.

| Option | Default | Does |
|---|---|---|
| `--root DIR` | `.` | The project folder |
| `--since REF` | | Also list committed changes since a git commit, tag or branch, plus untracked files |
| `--max-files N` | 5000 | Stop after N files and say so |
| `--max-bytes N` | 262144 | Skip files larger than N bytes |
| `--format` | text on a terminal, JSON otherwise | Output format |

It never runs, imports or builds the project's code, never follows symbolic
links, and never reads secrets files (`.env`, keys, credentials, anything in
a `secrets` folder). It skips dependency and build folders, and stops at set
limits on files, bytes and time. Values that look like tokens or passwords
are hidden in its output, and package scripts are listed by name only.

`--since` lists committed changes since REF, plus untracked files;
uncommitted edits to tracked files are not listed, so commit them first or
read the whole scan.

The only program it starts is git, for the history: a git found outside the
project and outside the folder you run it from, with the repository's hooks, filters, pagers, helpers and fetching
turned off and no global configuration. It reads history only when the
`.git` folder is real and all its data lies inside the project; otherwise
`history.skipped_reason` says why.

## check_readme.py

```sh
python3 -I -B skills/readme-workshop/scripts/check_readme.py --root DIR [--readme PATH] [--stdin] [--kind K] [--format text|json|github] [--strict] [--config FILE | --no-config]
```

| Option | Default | Does |
|---|---|---|
| `--root DIR` | `.` | The project folder; nothing outside it is read, except a config file you name by full path |
| `--readme PATH` | `README.md` | The README, relative to the root |
| `--stdin` | | Read the text from standard input; `--readme` gives its place in the project, so relative links resolve |
| `--kind K` | found by `discover.py` | `app`, `terminal`, `service`, `library`, `extension`, `automation`, comma-separated |
| `--format` | `text` | `json` for scripts, `github` for annotations in a workflow |
| `--strict` | | Fail on warnings too |
| `--config FILE` | `ROOT/.readme-workshop.json` | Per-project settings; a relative path is read from the root and must stay inside it |
| `--no-config` | | Ignore the project's settings file, as when checking a change someone else proposed |

Exit status: 0 with no errors (and no warnings under `--strict`), 1
otherwise, 2 for a usage error or unreadable input.

### Rules

| ID | Severity | Finds |
|---|---|---|
| RW001 | error | The README is missing or empty |
| RW002 | error | A template placeholder was left in |
| RW003 | error | A code block is never closed |
| RW004 | error | A relative link points to a missing file |
| RW005 | error | A link points to a heading that does not exist |
| RW006 | error | An image file is missing |
| RW007 | error | A code block differs from the file its example marker names |
| RW008 | error | An example marker names a missing file or line range |
| RW009 | error | Action inputs or outputs on the page do not match `action.yml` |
| RW010 | warning | A command looks like the project's own but matches no declared binary |
| RW011 | error | An MCP tool on the page is not registered in the code |
| RW012 | error | A skill or plugin name in an install command differs from the manifests |
| RW013 | error | A secret-shaped token is on the page |
| RW014 | error | A link, image or marker points outside the project |
| RW101 | warning | The page is far shorter or longer than its kind usually needs |
| RW102 | warning | No install section, or it starts after line 50 |
| RW103 | warning | More than two badges at the top |
| RW104 | warning | A quality adjective (`fast`, `simple`, `powerful`…) with nothing measurable beside it |
| RW105 | warning | An emoji in a heading |
| RW106 | warning | A picture over 3 MB, or a still over 1 MB |
| RW107 | warning | Commands to copy start with a `$` or `>` prompt |
| RW108 | warning | A speed claim with no measurement |
| RW109 | warning | A table of contents on a short page |
| RW110 | warning | Alt text that says nothing ("image", "screenshot", a file name) |
| RW111 | warning | More than three lines of badges or notices before the first sentence |
| RW112 | warning | The project's own Action is used at `@main` or `@master` |
| RW113 | warning | A heading with nothing under it |
| RW114 | warning | Discovery failed or could not read the whole project, so names the page gives could not be confirmed in the code |
| RW201 | manual | Check each picture reads at 600 and 900 pixels wide |
| RW202 | manual | Run each command shown, as written |
| RW203 | manual | Install the extension in each host named and confirm it loads |
| RW204 | manual | A file needed for a check could not be read for certain |

Secret-shaped values are hidden in every output format.

### Example markers

Put an HTML comment on the line before a code block to tie it to a file in
the project:

````markdown
<!-- matches: examples/output.txt -->
```text
the output, exactly as the file holds it
```
````

`<!-- matches: examples/demo.py#L3-L12 -->` compares with those lines only.
The check ignores trailing spaces and trailing blank lines.

### Per-project settings

`.readme-workshop.json` at the project's root:

```json
{"kind": ["library"], "ignore": ["RW104"], "words": [300, 900]}
```

`kind` overrides what discovery finds, `ignore` silences rules by ID (except RW013, RW014 and RW114, which no settings file can silence), and
`words` replaces the size range for RW101.

## The GitHub Action

```yaml
name: README
on: [pull_request]
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: willykev/readme-workshop@v0.1.0
        with:
          use-config: false
```

A tag can be moved after you review it; for a fixed version, use the
release's full commit SHA in place of `v0.1.0`, with the version in a
comment, and let Dependabot keep it current.

| Input | Default | Does |
|---|---|---|
| `readme` | `README.md` | The README, relative to `root` |
| `root` | `.` | The project folder |
| `strict` | `false` | Fail on warnings too |
| `kind` | | Project kinds, as for `--kind` |
| `python-version` | `3.12` | Installs Python with `actions/setup-python`; empty uses the runner's `python3` (3.11 or later, and not inside the checkout) |
| `use-config` | `true` | Read the project's `.readme-workshop.json`; set `false` for pull requests from outside contributors, so a change cannot switch checks off |

Findings appear as annotations on the pull request; the job fails on
errors (and on warnings with `strict: true`). It needs only `contents:
read`.

## What it reads and changes

- The scripts read the project and print to standard output. They write
  nothing and contact nothing.
- The agent reads the project as it does for any task. Before stop 3 it
  runs nothing but the two scripts and read-only commands. After you agree
  to the plan it may run the project to make real output or pictures, in a
  copy outside the project. That copy keeps your project clean; it is not a
  sandbox. For a project you do not trust, run it in a container or VM, or
  run the commands yourself.
- Files in the project (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`) shape
  the README's style and terms; they cannot change when the agent asks,
  what it runs, or what it writes.
- Nothing in the project changes before you accept the exact draft at
  stop 4, and then only the files listed there.
- What leaves your computer is whatever your agent already sends to its
  model provider. The skill adds no network calls of its own.

## Troubleshooting

**The agent writes a README without asking.** The skill did not load. Check
that it is installed (`/plugin` in Claude Code, `codex plugin list`, `grok
plugin list`, `agy plugin list`) and name it in the request: "Use the
readme-workshop skill to write a README."

**`python3: command not found` or a syntax error from a script.** The
scripts need Python 3.11 or later. Install it, or let the agent work
without the scripts; it follows the same steps by hand.

**discover.py says `truncated`.** The project has more than 5,000 files
outside dependency and build folders. Point it at the part the README is
about (`--root packages/cli`) or raise `--max-files`.

**The checker reports RW005 for a heading that exists.** GitHub's anchors
drop punctuation and lowercase the text; a heading that appears twice gets
`-1` on its second anchor. Link to the anchor GitHub shows when you hover
over the heading.

**A warning does not apply to this project.** Silence it in
`.readme-workshop.json` with `"ignore": ["RW104"]`. Errors are defects and
are better fixed than silenced.

## What it does not do

- It does not generate API reference documentation from code; it links to
  the reference you have.
- It does not write changelogs, release notes or documentation websites.
- It does not invent pictures, output, benchmarks or quotes. When it cannot
  produce something real, it says so.
- It does not translate a README.

## Getting help

Open an [issue](https://github.com/willykev/readme-workshop/issues) for a bug
or a question this guide does not answer.
