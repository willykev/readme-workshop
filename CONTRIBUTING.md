# Contributing

The skill is plain Markdown and Python with no dependencies. Python 3.11 or
later runs the scripts and the tests.

## Layout

| Path | What it is |
|---|---|
| `skills/readme-workshop/SKILL.md` | The instructions an agent loads |
| `skills/readme-workshop/references/` | Pages the skill opens when it needs them, one hop from `SKILL.md` |
| `skills/readme-workshop/assets/` | The README and guide templates |
| `skills/readme-workshop/scripts/` | `discover.py`, `check_readme.py` and the modules they share |
| `plugin.json`, `.claude-plugin/` | Plugin manifests for Claude Code, Codex, Antigravity and Grok |
| `action.yml` | The GitHub Action around `check_readme.py` |
| `tests/` | Unit tests and fixtures (fixture skills are stored as `SKILL.md.in`, so skill installers do not list them) |

## Test

```sh
bin/test
```

It runs the unit tests, then `claude plugin validate --strict`, `agy plugin
validate --strict` and `grok plugin validate` for any of those that are
installed. CI runs the unit tests on Linux, macOS and Windows with Python
3.11 and 3.13.

## Rules for the skill text

- `SKILL.md` stays under 250 lines; detail goes in `references/`, linked
  directly from `SKILL.md` (never from one reference to another's
  references).
- Frontmatter uses only the fields of the Agent Skills specification, and
  no syntax that works in one host only.
- Examples in the text are made up. No real project's README is quoted.

## Rules for the scripts

- Standard library only. They read; they never write, prompt, or run the
  code of the project they look at.
- Every finding has a stable rule ID. Changing what a rule means is a
  breaking change: give it a new ID instead.
- A false error on a good README is worse than a missed warning.

## Release

1. Update `VERSION`, the `version` in `plugin.json` and
   `.claude-plugin/plugin.json`, and add a dated section to `CHANGELOG.md`.
2. Run `bin/test`.
3. Tag `vX.Y.Z`, push the tag, and publish a GitHub release with the
   changelog section as its notes.
