# readme-workshop

readme-workshop is an agent skill that helps you write, review, and update
a project's README in Claude Code, Codex, Grok, Antigravity, and other
agents that support Agent Skills. It reads your codebase, works through the
audience, key features, and outline with you step by step, and does not
touch any files until you approve the final draft.

[Install](#install) · [Guide](docs/guide.md) · [Changelog](CHANGELOG.md)

In any project, ask your agent:

> Use readme-workshop to write a README for this project.

It inspects the repository first and comes back with what it found so you
can correct anything before it plans the page. Here is its first reply in a
real Claude Code session on a sample recipe tool called cookconv (trimmed;
see the [full reply](docs/example-session.md)):

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

You need an agent that can read files and run shell commands. The two
bundled scripts need Python 3.11 or later; without Python, the skill still
works with fewer automated checks. In Claude Code:

```sh
claude plugin marketplace add willykev/readme-workshop
claude plugin install readme-workshop@readme-workshop
```

Start a new session, then run `claude plugin list` to confirm it is enabled.

<details>
<summary>Codex, Grok, Antigravity, and other agents</summary>

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

To test local changes from a clone, start Claude Code with
`claude --plugin-dir path/to/readme-workshop`.

Update with `claude plugin update readme-workshop`, disable with
`claude plugin disable readme-workshop`, or remove with `claude plugin
uninstall readme-workshop` followed by `claude plugin marketplace remove
readme-workshop`. It leaves nothing else behind. See the
[guide](docs/guide.md#update-switch-off-and-remove) for the equivalent
commands in each agent.

## Write your first README

In your project, ask: **"Use readme-workshop to write a README for this
project."** The agent inspects the codebase and pauses four times for your
input:

1. **What it found:** what the project does, who it is for, how to install
   it, the first useful result, and anything it could not determine from
   the code.
2. **What to highlight:** 8 to 12 candidate features with file-and-line
   evidence, with its recommended picks marked.
3. **The plan:** three one-sentence pitches to choose from, the section
   order, and how it plans to demonstrate the project working.
4. **The final draft:** the complete README, every file it will add or
   change, the checker's output, and any claims it could not verify.

Reply "ok" to accept a stop, or tell it what to change. Nothing is written
until you approve the draft at stop 4. Saying "just write it" skips ahead
to stop 4, and it still asks before writing. The other modes work the same
way:

| Ask it to | What it does | Files changed |
|---|---|---|
| Improve or rewrite the README | Runs the four stops and shows where each section of the old README goes | Only the files you approve at stop 4 |
| Review the README | Reports claims that don't match the code, what is missing, and the three highest-impact edits | None |
| Update the README after changes | Proposes updates only for what changed since the last commit that touched the README | Only the files you approve |
| Make screenshots or examples | Runs stops 3 and 4, capturing real output in a temporary copy of the project | Only the files you approve |
| Write the user guide | Runs the same four stops for `docs/guide.md` | Only the files you approve |

## Features

- **Every claim backed by code.** Scans your repository for CLI commands,
  exports, MCP tools, Action inputs, and install methods with file and line
  numbers, then verifies every sentence against the source before showing
  you a draft.
- **Real output, never fabricated.** Captures command output and
  screenshots by running your project in a temporary copy, and uses comment
  markers to keep README code blocks in sync with files in your repo.
- **Works for any kind of project.** Supports desktop and web apps,
  command-line tools, services, libraries, agent skills and plugins, MCP
  servers, and GitHub Actions.
- **Built-in CI checker.** `check_readme.py` catches broken links and
  anchors, leftover placeholders, stale examples, accidental secrets, and
  mismatched Action inputs, MCP tools, binaries, or plugin and skill names.

## Check a README in CI

The checker runs as a GitHub Action and reports findings as pull request
annotations. It fails the job on errors, and on warnings when `strict:
true`. It only needs `contents: read`:

```yaml
- uses: willykev/readme-workshop@v0.1.4
  with:
    use-config: false   # recommended for pull requests from forks
```

All six inputs are optional; the [guide](docs/guide.md#the-github-action)
lists them and explains how to pin by commit SHA instead of a tag. To run
the same checks locally from a clone of this repo against a sibling project:

```sh
python3 -I -B skills/readme-workshop/scripts/check_readme.py --root ../my-project --readme README.md
```

It exits 1 on errors (and on warnings with `--strict`). See the
[guide](docs/guide.md#rules) for the full list of rules.

## What it touches

- **Read-only scripts.** `discover.py` and `check_readme.py` only read
  inside the target project (plus a config file you pass via `--config`)
  and never write to it. They never execute project code; the only external
  command they run is `git`, with repo hooks, filters, and helpers disabled.
  Values that look like secrets are redacted from their output.
- **Isolated runs.** The agent only runs your project after you approve it
  at stop 3, and always in a temporary copy outside your repo. That keeps
  your working tree clean, though it is not a security sandbox — for
  untrusted code, use a container or run the commands yourself.
- **Explicit writes.** It only writes files you approved at stop 4, unless
  you explicitly ask it to [work without questions](docs/guide.md#work-without-questions);
  even then, it never overwrites an existing README.
- **No network calls from scripts.** Neither script makes network requests.
  Anything the agent needs to fetch to build or run your project is part of
  the plan you approve at stop 3.

## Limits

- It can only capture what can run in your agent's environment. A desktop
  app needs a way to render its own window or a capture script; if neither
  is available, the draft notes the gap instead of faking a screenshot.
- It does not generate API references, changelogs, or documentation sites;
  it links to the ones you already have.
- Verification is only as thorough as the agent running it, which is why
  any claim it could not verify is listed explicitly at stop 4.

## More

The [guide](docs/guide.md) covers every mode, both scripts, all checker
rules, the GitHub Action, and troubleshooting. See the
[changelog](CHANGELOG.md) for releases, [CONTRIBUTING](CONTRIBUTING.md) to
contribute, and the [MIT license](LICENSE).
