# readme-workshop

readme-workshop is a skill for coding agents that writes, reviews and
updates a project's README with you. It reads the code, agrees on the reader,
the highlights and the plan with you one step at a time, checks every claim
against the code, and changes nothing until you have seen the exact page.
It works in Claude Code, Codex, Antigravity, Grok and other agents that
read Agent Skills.

[Install](#install) · [Guide](docs/guide.md) · [Changelog](CHANGELOG.md)

Here the checker catches a sample MCP server's README listing a tool its code never registers:

```sh
python3 -I -B skills/readme-workshop/scripts/check_readme.py --root tests/fixtures/check/mcp-server --readme README-bad.md
```

<!-- matches: docs/check-example.txt -->
```text
README-bad.md: warning RW101 The page has 42 prose words; an extension README reads best with 200 to 1600.
    Fix: Add what an installer needs to know.
README-bad.md: manual RW203 This is an extension.
    Fix: Install it in each host the README names and confirm it loads there.
README-bad.md:8: manual RW202 The page shows commands.
    Fix: Run each one as written, in a scratch folder, and confirm it does what the page says.
README-bad.md:17: error RW011 The tool delete_note is not registered in the code.
    Fix: Use the registered name (add_note, search_notes), or remove the row.
1 error, 1 warning, 2 manual checks (extension; 42 words).
```

## Features

- **Reads the code first.** A scanner lists what the project is and what a
  user meets (commands, exports, tools, Action inputs, install channels),
  with the file and line for each.
- **Four stops, then the page.** The reader and the job, the highlights,
  the plan, and the exact draft. Nothing in your project changes until you
  say yes to the last one.
- **Evidence for every claim.** Each sentence is checked against the code
  before you see the draft; what could not be checked is listed.
- **Any kind of project.** Apps, command-line tools, services, libraries,
  agent skills and plugins, MCP servers and GitHub Actions.
- **Real output only.** Examples and pictures come from runs in a scratch
  copy, and example markers keep each block equal to a file in the project.
- **A checker for CI.** `check_readme.py` finds broken links and anchors,
  leftover placeholders, stale examples, Action inputs that do not match
  `action.yml`, and secrets, locally or as a GitHub Action.

## Install

You need an agent that can read files and run shell commands. The two
scripts need Python 3.11 or later; without it the skill still works, with
less checking.

In Claude Code:

```sh
claude plugin marketplace add willykev/readme-workshop
claude plugin install readme-workshop@readme-workshop
```

In Codex:

```sh
codex plugin marketplace add willykev/readme-workshop
codex plugin add readme-workshop@readme-workshop
```

In Grok, `grok plugin install willykev/readme-workshop --trust`. In
Antigravity, `agy plugin install https://github.com/willykev/readme-workshop`.
For any agent the GitHub CLI supports, `gh skill install
willykev/readme-workshop readme-workshop --agent AGENT`.

Start a new session afterward. The [guide](docs/guide.md#install) has the
commands to update and remove it in each agent.

## Write your first README

In a project, ask your agent: **"Write a README for this project."** It
reads the code, then stops four times:

1. **What I found:** what the project is, who it is for, how it installs,
   the first result, and what it could not tell from the code.
2. **What to highlight:** eight to twelve candidates with their evidence;
   it marks the ones it recommends.
3. **The plan:** three pitches, the sections, and how it will show the
   project working.
4. **The exact draft:** the whole page, every file it would add, and the
   claims it could not verify.

Reply "ok" to accept a stop, or say what to change. It writes only after you
accept the draft at stop 4. "Just write it" skips to stop 4; it still asks.

Ask it to **review** a README and it reports what to fix without editing
anything. Ask it to **update** one after a release and it changes only what
the code changed.

## Check a README

The checker reads a README and the project around it, as in the run at the
top of this page. From a clone of this repository, on a project beside it:

```sh
python3 -I -B skills/readme-workshop/scripts/check_readme.py --root ../my-project --readme README.md
```

It exits 1 on errors (and on warnings with `--strict`). In a workflow, the
same checks run as an Action and show up on the pull request:

```yaml
- uses: willykev/readme-workshop@v0.1.0
  with:
    use-config: false   # for pull requests from outside contributors
```

The [guide](docs/guide.md#check_readmepy) lists every rule.

## What it touches

- The scripts read only inside the project. They never run its code, and
  the only program they start is git, with the repository's own hooks,
  filters and helpers turned off. Values that look like secrets are hidden
  in their output.
- The agent runs the project only after you agree to it at stop 3, in a
  copy outside the project. That copy keeps your project clean but is not a
  sandbox: for code you do not trust, use a container, or run the commands
  yourself.
- It writes only the files you accepted at stop 4.
- The scripts make no network calls. Anything the agent fetches to build
  or run the project is part of the plan you agree to at stop 3.

## Limits

- It shows only what it can run where your agent runs. A desktop app needs
  a way to draw its own window, or a capture script; when there is none, the
  draft says so instead of faking a picture.
- It does not write API references, changelogs or documentation sites; it
  links to the ones you have.
- The result is only as careful as the agent running it, which is why every
  claim it could not verify is listed at stop 4.

## More

The [guide](docs/guide.md) covers each mode, both scripts and every rule,
the Action, and troubleshooting. See the [changelog](CHANGELOG.md) for what
is new, [CONTRIBUTING](CONTRIBUTING.md) to change the skill, and the
[MIT license](LICENSE).
