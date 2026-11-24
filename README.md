# readme-workshop

readme-workshop is an agent skill that writes, reviews and updates a
project's README with you, in Claude Code, Codex, Grok, Antigravity and other
agents that read Agent Skills. It reads the code, settles the reader, the
highlights and the plan with you one step at a time, and changes nothing
until you have seen the exact page.

[Install](#install) · [Guide](docs/guide.md) · [Changelog](CHANGELOG.md)

In a project, ask your agent:

> Use readme-workshop to write a README for this project.

It reads the code and comes back with what it found, for you to correct
before it plans anything. This is its first reply in a real Claude
Code session, on a small sample recipe tool called cookconv (trimmed; the
[whole reply](docs/example-session.md)):

> **What I found (stop 1 of 4)**
>
> cookconv scales plain-text recipes to a different number of servings and
> converts their units between US and metric. You can use it as a
> command-line tool or as a Python library.
>
> - …
> - **Your files:** it only reads the recipe you name. It writes a file only
>   when you pass `-o` (`cli.py:18`, `cli.py:26`), and it makes no network
>   calls.
> - **Couldn't tell:** whether it's published on PyPI (there's no release
>   workflow or repository URL), and which reader the page should address
>   first. There's no existing README, changelog or test suite to go on.
>
> Is this right? Correct anything that isn't, and answer these:
> 1. Is cookconv on PyPI? If not, I'll show how to install it from a clone
>    with `pipx install .`.
> 2. Which reader should the page address first, cooks or developers? If
>    you're not sure, I'll lead with cooks and add a short "From Python"
>    section.

## Install

You need an agent that can read files and run shell commands. The skill's
two scripts need Python 3.11 or later; without it the skill still works,
with less checking. In Claude Code:

```sh
claude plugin marketplace add willykev/readme-workshop
claude plugin install readme-workshop@readme-workshop
```

Start a new session; `claude plugin list` shows it as enabled.

<details>
<summary>Codex, Grok, Antigravity and other agents</summary>

```sh
# Codex
codex plugin marketplace add willykev/readme-workshop
codex plugin add readme-workshop@readme-workshop

# Grok
grok plugin install willykev/readme-workshop --trust

# Antigravity
agy plugin install https://github.com/willykev/readme-workshop

# Any agent the GitHub CLI supports (replace claude-code with yours)
gh skill install willykev/readme-workshop readme-workshop --agent claude-code
```

</details>

To try a change from a clone, start Claude Code with
`claude --plugin-dir path/to/readme-workshop`.

Update with `claude plugin update readme-workshop`; switch it off with
`claude plugin disable readme-workshop`; remove it with `claude plugin
uninstall readme-workshop`, then `claude plugin marketplace remove
readme-workshop` to forget the catalog. It keeps nothing else. The
[guide](docs/guide.md#update-switch-off-and-remove) has the same for each agent.

## Write your first README

Ask in a project: **"Use readme-workshop to write a README for this
project."** It reads the code, then stops four times:

1. **What I found:** what the project is, who it is for, how it installs,
   the first result, and what it could not tell from the code.
2. **What to highlight:** eight to twelve candidates with their evidence;
   it marks the ones it recommends.
3. **The plan:** three pitches, the sections, and how it will show the
   project working.
4. **The exact draft:** the whole page, every file it would add, and the
   claims it could not verify.

Reply "ok" to accept a stop, or say what to change. It writes only after you
accept the draft at stop 4. "Just write it" skips to stop 4, and it still
asks. It handles the other README jobs the same way:

| Ask it to | It does | Changes in your project |
|---|---|---|
| Improve or rewrite the README | The four stops, plus where each part of the old page goes | The files you accept at stop 4 |
| Review the README | A report: claims that don't match the code, what is missing, the three changes that matter most | Nothing |
| Update the README after changes | Proposes only what changed since the commit that last touched the README | The files you accept |
| Make screenshots or examples | Stops 3 and 4 only, with real runs in a copy of the project | The files you accept |
| Write the user guide | The same stops, for `docs/guide.md` | The files you accept |

## Features

- **Evidence for every claim.** A scanner lists what a user meets
  (commands, exports, tools, Action inputs, install channels) with the file
  and line for each, and each sentence is checked against the code before
  you see the draft.
- **Real output only.** Examples and pictures come from runs in a scratch
  copy, and an example marker keeps a block equal to a file in the project.
- **Any kind of project.** Apps, command-line tools, services, libraries,
  agent skills and plugins, MCP servers and GitHub Actions.
- **A checker for CI.** `check_readme.py` finds links to missing files and
  headings, leftover placeholders, examples that no longer match their
  file, names that don't match the code, and secrets.

## Check a README in CI

The checker runs as a GitHub Action and shows its findings as annotations
on the pull request. The job fails on errors, and on warnings with
`strict: true`. It needs only `contents: read`:

```yaml
- uses: willykev/readme-workshop@v0.1.1
  with:
    use-config: false   # for pull requests from outside contributors
```

All six inputs are optional; the [guide](docs/guide.md#the-github-action)
lists them, with how to pin a commit instead of a tag. To run the same
checks locally, from a clone of this repository on a project beside it:

```sh
python3 -I -B skills/readme-workshop/scripts/check_readme.py --root ../my-project --readme README.md
```

It exits 1 on errors, and on warnings with `--strict`. The
[guide](docs/guide.md#rules) lists every rule.

## What it touches

- The scripts read only inside the project (and a settings file you name
  with `--config`) and write nothing to it. They never run its code, and
  the only program they start is git, with the repository's own hooks,
  filters and helpers turned off. Values that look
  like secrets are hidden in their output.
- The agent runs the project only after you agree to it at stop 3, in a
  copy outside the project. That copy keeps your project clean but is not a
  sandbox: for code you do not trust, use a container, or run the commands
  yourself.
- It writes only the files you accepted at stop 4, unless you asked it to
  [work without questions](docs/guide.md#work-without-questions); even then
  it never replaces an existing README.
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
