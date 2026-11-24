# The page, top to bottom

Contents: [Shape](#shape) · [Name and pitch](#1-name-and-pitch) ·
[Link row](#2-link-row) · [Show it working](#3-show-it-working) ·
[Features](#4-features) · [Install](#5-install) · [First use](#6-first-use) ·
[More for the interested](#7-more-for-the-interested) · [Writing](#writing) ·
[What stays out](#what-stays-out) · [Sizes](#sizes)

The kind files hold what differs by kind. The best pages belong to small projects that do the whole
job on one page; famous projects often have thin READMEs because a website
does their selling.

## Shape

| Part | Size | Answers |
|---|---|---|
| Name and pitch | 1 to 3 sentences | What is it? |
| Link row | 1 line, 3 or 4 links | Where is everything? |
| Show it working | 1 picture, or a real input and its output | What does it look like in use? |
| Features | 4 to 7 bullets | What can it do? |
| Install | 1 command block, then alternatives | How do I get it? |
| First use | 1 first step, then 3 to 5 short blocks | What do I do first? |
| More for the interested | as needed: commands, configuration, performance, data, limits | Is it fast, safe, honest? |
| More | 2 or 3 lines | Where is the manual? |

Drop any part the project has nothing to say for. A tool that does one
thing can drop the feature list and let the first-use section carry it. The
sizes are guides (see [Sizes](#sizes)): going a little over is fine when the
extra earns its place.
The kind file says which parts a kind needs and in what order.

## 1. Name and pitch

The first sentence names a plain category, what it works with, and the
difference. A second sentence may say what it does in the user's verbs, or
make a promise the reader can test. A third may state a stance: local, no
account, no telemetry.

Formulas that work (made-up examples):

- **Category, platform, difference.** "A photo organizer for Windows and
  macOS that groups pictures by trip instead of by folder."
- **Then what it does, in verbs.** "Inkwell is a clipboard manager for
  macOS. It keeps what you copy and lets you search and paste it again."
- **Then a promise that can be checked.** "Opening a new window never
  resizes the ones already open."
- **A known thing plus the difference**, for a tool that stands in for a
  standard command: "A `cat` for CSV files that lines up the columns."
- **Does X without Y.** "Share files with devices on your network without
  an internet connection."
- **For code people import:** what it does, for which runtime, and the
  difference: "Typed validation for TypeScript that compiles to plain
  functions, with no runtime dependency."
- **For an extension:** the host, what it adds, and when it acts: "A Claude
  Code skill that writes commit messages from the staged diff when you ask
  it to commit."

Rules:

- Use the noun people search for: editor, reminders app, HTTP client,
  validation library, MCP server, GitHub Action. "Platform", "solution",
  "framework for X" and "ecosystem" say nothing.
- Name what it works with: the desktop, the host, the runtime.
- No adjective the next line does not prove. Out: fast, simple, powerful,
  modern, beautiful, seamless, blazing, next-generation, lightweight.
- Name no other product to place this one ("like X but…") unless the
  owner asks for it. Say what it is in its own terms.
- Leave the implementation language and toolkit out of the pitch, unless
  the reader must match it (a library's runtime). Turn a toolkit choice into
  a benefit with a number: a package size, a start time.
- The first sentence, trimmed, is the repository's About line.

## 2. Link row

One line under the pitch, three or four links, in-page first:

```markdown
[Install](#install) · [Guide](docs/guide.md) · [Changelog](CHANGELOG.md) · [Releases](https://github.com/OWNER/REPO/releases)
```

Link only what exists. No table of contents: GitHub shows an outline, and
on a page this size a list of headings is noise.

Badges: none, or at most two that tell a user something to act on (latest
version, package registry). A build badge is for contributors and can sit at
the bottom. Star counts, download charts and activity badges tell a
newcomer nothing.

## 3. Show it working

The first picture or example after the pitch. It answers "what does it look
like in use?" with something real.

- **An app:** a short loop of the action that explains the pitch, or a
  still of a finished result if the result is what a visitor needs to
  inspect. See [pictures](pictures.md).
- **A terminal tool:** a command and its real output, as text in a code
  block (copyable, searchable), or a short recording when the output moves.
- **A library:** the smallest program that does the main job, and what it
  prints.
- **An extension:** the request a user makes and what the host does, or the
  command and its result; for a tool provider, the tool table.
- **Automation:** the snippet to paste and what a run reports.

It must come from a real run. See [proof](proof.md).

## 4. Features

About four to seven bullets a reader takes in within ten seconds; one more
is fine if it is something a newcomer would ask about. Each has a bold
label of two to four words, then one sentence saying what the user can now
do, with the key, command or literal input where that helps.

```markdown
- **Typed dates.** `Call the bank tomorrow at 9` becomes a reminder with a date and a time.
- **Every unit.** `--to metric` converts cups, ounces and °F in one pass.
```

- Start from what the user does or gets, not from how it is built.
- Give the mechanism only when it is the reason for a promise: "reads the
  file once and never writes to it", "no network access at all".
- A bullet that restates an adjective is worse than none ("Easy to use").
- Past about twelve bullets nobody reads them. The full list goes in the
  guide; end the list with a link to it if there is more.
- No emoji bullets.
- Most distinctive first.

## 5. Install

Start the install section within the first fifty lines or so; the best
small projects reach it before line 45. Patterns per channel are in
[install](install.md).

- Lead with the route most people should take, as one block that can be
  copied and run as it stands. No placeholders in the main block.
- One line of requirements above it: system and version, runtime, host.
- Print the literal command, for the package manager the readers use.
- Say what happens next: where the app appears, the command that starts
  it, the URL to open, how to check it worked.
- Call out a name mismatch: "The package is `cookconv-cli`; the command is
  `cookconv`."
- Number any step after installing that is not optional (a service to
  enable, a line to add to a config file, a key to bind, a secret to set).
  Say what it changes and how to undo it.
- Build from source in five lines or fewer.
- One line each for updating and for removing it.

## 6. First use

Name the section for the first thing people do ("Scale your first recipe",
"Make your first request", "Call it from Python"). Then:

1. **The first step**, in two or three sentences: the command or key, the
   input, what appears. One action, start to finish.
2. **Three to five short blocks**, most used first: a small heading naming
   the task, one or two sentences with the command or key, then the proof
   (picture, output, snippet). Text first, proof after.
3. **For an app with keys**, a table of ten to twelve keys that get someone
   through the first day, and how to see the rest.

## 7. More for the interested

Each of these only if the project has something true to say:

- **Commands** (an app or service with a command line): one sentence on what
  it is for, four to eight real invocations with a comment on each, and
  where the rest are. Mention `--json` if it exists.
- **Configuration:** the snippet to paste, labeled with the version it is
  for; up to eight options with defaults; the rest in the guide.
- **Performance:** three or four measured facts with the machine and the
  method. See [claims](claims.md). Leave the section out if nothing was
  measured.
- **Your data / What it touches:** where data lives, in what format, how to
  back it up, every time it uses the network, what access it gets. See
  [claims](claims.md).
- **Limits:** what it does not do, and the way around it if there is one.
  It reads as competence and saves a disappointed install.

## 8. More

One sentence naming what the guide holds, then the changelog, how to
contribute, and the license on one line:

```markdown
The [guide](docs/guide.md) covers every command and setting, backups and troubleshooting. See the [changelog](CHANGELOG.md), [CONTRIBUTING](CONTRIBUTING.md) to build or change it, and the [MIT license](LICENSE).
```

## Writing

Write for a human reader, the way you would explain the project to a colleague out loud:

- **Natural first, concise second.** Plain and honest does not mean stiff or
  telegraphic. Cutting hype means cutting empty adjectives ("blazing",
  "seamless"), not cutting normal phrasing. If a sentence feels cramped or
  nobody would say it out loud, rewrite it:
  - *Stiff:* "It settles the reader, the highlights and the plan with you."
    *Natural:* "It works through the audience, key features, and outline with you."
  - *Stiff:* "A scanner lists what a user meets."
    *Natural:* "A scanner finds the commands, exports, and options users interact with."
  - *Stiff:* "An example marker keeps a block equal to a file."
    *Natural:* "Comment markers keep code examples in sync with files in your repo."
- **Leave workshop jargon out.** Terms like "decision card", "surfaces",
  "enabler", or "proof" are for your own notes, not the finished README. Use
  the everyday words a reader expects ("screenshots" or "demos" instead of
  "pictures", "users" or "readers" instead of "strangers" or "installers").
- Address the reader directly in plain words: "Run", "your recipes",
  "nothing to configure".
- Prefer the specific: a key, a path, a number, an input the reader could
  type.
- Direct statements read as trustworthy: "It never connects to the network."
- Keys in backticks or `<kbd>`, one style per page. Commands in code
  spans.
- No inside jokes, no filler ("and much more", "whether you're a beginner or
  an expert").
- Use the project's spelling and terms as its code and interface use them.

## What stays out

| Leave out of the README | Where it goes |
|---|---|
| Every command, option, key and setting | `docs/guide.md` |
| Build, test and release steps, CI, tooling | `CONTRIBUTING.md` |
| What changed in each version | `CHANGELOG.md`, release notes |
| How it works inside, architecture | Nowhere, unless a user must act on it; then one short guide section |
| Why it was designed this way, what was considered | Nowhere |
| Plans and promises | Nowhere; say what it does today |
| Thanks, credits, dependency lists | `LICENSE`, a notices file, or one line at the bottom |
| Badge walls, star charts, contributor grids, a table of contents, emoji headings | Nowhere |

A stance may stay when it is one sentence a user can rely on ("No account,
ever.").

## Sizes

Every size here is a rough guide, not a limit. A bullet more than the guide,
or a few hundred words more, is fine when each one earns its place: it
answers something a reader deciding whether to install would ask. Cut what
repeats, explains internals, or would sit better in the guide; do not cut
what a reader needs to get started or to trust the page. The checker only
warns well past the range.

| Kind | Words | Lines | Pictures |
|---|---|---|---|
| App | 500 to 800 | 120 to 180 | 4 to 6 |
| Terminal | 400 to 800 | 80 to 160 | 0 to 3 (output as text counts as proof) |
| Service | 500 to 900 | 100 to 180 | 1 to 3 |
| Library | 300 to 1,000 | 100 to 250 | 0 to 1 |
| Extension | 400 to 1,000 | 80 to 200 | 1 to 2 (or real output as text) |
| Automation | 400 to 1,100 | 100 to 250 | 0 to 1 |

Extensions and automation often run long because they carry their whole
reference on the page; the targets above leave the catalog to the guide.
A clean first screen has no more than three badges.
