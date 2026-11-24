# Discover: find what an installer cares about

Contents: [The scanner](#the-scanner) · [The decision card](#the-decision-card) ·
[Where to look](#where-to-look) · [Candidates](#candidates) ·
[Scoring](#scoring) · [The three bins](#the-three-bins) ·
[What is not a feature](#what-is-not-a-feature) · [By hand](#by-hand)

The code says what a project can do. It does not say which of those things
a stranger cares about. Work from both sides: from the reader (what must
they decide before installing?) and from the code (what does it actually
do, and what does a user see?). Meet in the middle with evidence.

## The scanner

```sh
python3 -I -B scripts/discover.py --root PROJECT_DIR --format json
```

Read its output as a map, not an answer. It lists what is declared in the
code with path and line; it does not rank, and it misses anything built at
run time (`skipped` entries with reason `dynamic`), files it could not read
(`unreadable`, `too-large`), and registrations past its limits (`capped`).
Treat each of those as something to check by hand, never as proof that a
feature is absent. `history.skipped_reason` says when it left git history
out (a partial clone, git data outside the project, no temporary folder). Check `truncated` and
`skipped`: a large repository may need a second run on a sub-folder
(`--root packages/cli`).

For a later run, `--since REF` adds what was committed since REF, including
renames and deletions, plus untracked files; edits not yet committed are not
listed, so read the working files for those. Use the commit that last changed
the README (`history.last_readme_commit`).

## The decision card

Before ranking anything, write down what the reader must decide. Pick the
role the project mostly serves; a project can serve two.

| Role | Who | Must decide | Card fields |
|---|---|---|---|
| Installer | Someone who will run it (app, terminal tool) | Does it run on my system? What do I get in the first minute? Where does my data go? | Platforms and versions; install route; first result; data location and network use; what it does not do |
| Integrator | A developer who will import or call it (library, SDK, API) | Does it fit my runtime and stack? What does the first call look like? What does it cost me? | Language and runtime versions; package name; the smallest working call and its result; dependencies and size; stability (version, breaking-change policy); license |
| Operator | Someone who will host it (service, self-hosted app, cloud stack) | Can I deploy it here? What does it need? What will it cost me? How do I keep it running and get my data back? | Deployment routes and their order (setup, deploy, post-deploy steps); required services (database, queue); accounts and hosting limits; ports; configuration and secrets; persistent state; backup and upgrade; what it costs to keep running; how to tear it down and what survives |
| Enabler | Someone who will switch it on inside a host (skill, plugin, MCP server, extension, Action, hook) | Does it work in my host? What access does it get? When does it act, and what does it change? | Hosts and versions; install command per host; permissions, tools and network it uses; what triggers it; what it changes; how to turn it off |

Fill each field with a found value, a guess with its reason, or "cannot
know". The card is the spine of stop 1, and every empty field is either a
question at stop 1 or a gap the README must not paper over.

## Where to look

Read the project's rules and existing documents first, then the manifest,
then the surfaces for its kind. A surface is a place where a user meets
the project.

| Kind | Surfaces to read | The visible effect to trace to |
|---|---|---|
| App | Main window and views (SwiftUI, XAML, React routes, QML, GTK builders); menus, actions and their shortcuts; settings; the `.desktop` entry, app manifest; sample data in `examples/` | What appears on screen, what is saved where |
| Terminal | The argument parser (argparse, click, typer, clap, cobra, commander, yargs); subcommands and options; `--help` text in the source; man pages; shell completions; config file format; output formats (`--json`) | What a command prints or changes |
| Service | Routes and handlers; the Dockerfile and compose file (ports, volumes, environment); configuration and environment variables; migrations; health checks; admin commands | The first request that works and what it returns; what persists |
| Library | Public exports (`__all__`, `index.ts` exports, `pub` items in `lib.rs`, exported Go identifiers); type signatures; `examples/`; doc comments; tests that read like usage | The smallest program that does the main job, and its output |
| Extension | Skill `SKILL.md` files; plugin manifests; slash commands; hooks and their events; MCP tool registrations and their schemas; contributed editor commands and settings; browser permissions | A real prompt or command and what the host does with it; the permissions granted |
| Automation | `action.yml` (inputs, outputs, `runs`); workflow files; `.pre-commit-hooks.yaml`; hook scripts | The snippet a user pastes, and what a run reports or changes |

Also read, for every kind:

- **`CHANGELOG.md` and release notes.** What the authors chose to announce
  is a strong signal of what matters to them.
- **Examples and end-to-end tests.** Usage that is exercised is usage that
  works.
- **The existing README and docs**, even when they are poor: they hold the
  owner's own description and often facts not visible in code.
- **Issues or discussions folders** if present in the tree (templates
  show what users ask about).

Trace each candidate to its visible effect. A function nobody can reach
from an entry point is not a feature. A setting nobody can change from the
interface or a config file is not a feature.

## Candidates

List 8 to 12 candidates. Merge detail into something a user does: "export
to PDF", "export to HTML" and "export to Markdown" are one candidate,
"Export to PDF, HTML or Markdown". Phrase each as a benefit in the user's
verbs, with the evidence beside it:

```text
3. Typed dates become reminders: "lunch tomorrow at 1" sets the date and time.
   found: src/parse/dates.rs:14 (parse_natural), tests/dates.rs (31 cases)
```

## Scoring

Score each candidate 0 to 2 on three things, then rank by
`2 × first task + decision value + proof`:

| Score | First task | Decision value | Proof |
|---|---|---|---|
| 2 | Part of the default first run: the main window, the main command, the first call | Settles a decision-card field (platform, data, access, runtime) or is the project's difference | An example, an end-to-end test, a sample file or a real run shows it |
| 1 | One step from the first run | Nice to know before installing | Unit-tested or clearly wired from an entry point |
| 0 | Advanced or rare | Only matters after installing | Only declared; not traced |

Raise a candidate one place when the changelog announced it, the existing
description names it, or the owner's rules mention it. Recommend the top 4
to 7 for the feature list. Keep the rest for the guide.

## The three bins

Every item on the decision card and every candidate sits in one bin:

- **found**: you can point to path:line or to output you produced.
- **guessed**: you are inferring (from a name, a folder, a dependency). Say
  what you inferred from.
- **cannot know**: only the owner knows. Audience and motive, what is not
  ready, what is deliberately left out, the preferred install route when
  there are several, whether a claim about speed was measured, the
  project's future.

Separately, mark how far each item was checked: **ran** (you ran it and
saw the result), **source-traced** (followed from an entry point to the
effect), or **untested**. The page may only state as fact what is found;
untested items are stated with care or confirmed by the owner.

## What is not a feature

Never present these as features:

- Names starting with `_`, internal or private modules, anything marked
  internal, debug or experimental, and helpers only used by tests.
- Commands, flags or tools registered only under `tests/`, `examples/`
  (as demos), `scripts/dev`, or behind a debug build.
- Commented-out code, disabled feature flags, stubs, `TODO` handlers.
- Dependencies and frameworks ("built with X") unless they change what the
  user gets; then say what changes ("works offline", "a 2 MB binary").
- Anything only a contributor sees: the test suite, CI, linting, code
  structure.

## By hand

Without Python 3.11, do what the scanner does with the shell: list the
tree with `find PROJECT_DIR -path '*/.git' -prune -o -type f -print` (find
does not follow links by default), skipping `node_modules`, `vendor`,
`dist`, `build`, `target` and virtual environments; read the manifests; and
search the surfaces listed above (`grep -rn` for parser declarations,
exports, registrations). Avoid git commands in a project you do not trust:
its own configuration can make git run programs. Never read secrets files
(`.env`, keys, credentials), and never run the project's code before the
person agrees to it at stop 3.
