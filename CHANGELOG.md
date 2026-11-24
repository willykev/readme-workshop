# Changelog

## 0.1.4 — 2026-11-23

- Fixed a race in `discover.py`'s `run_git()` that could kill a healthy `git`
  process between stdout EOF and process exit.
- Fixed `check_readme.py` rule `RW012` raising false errors on `OWNER/REPO`
  and URL plugin install commands (such as Grok and Antigravity installs).
- Reconfigured `sys.stdout` and `sys.stderr` to UTF-8 in `discover.py` so
  non-ASCII repo metadata does not crash on Windows / non-UTF-8 locales.
- Passed the pinned `safety.Tree` handle into `image_size()` during
  discovery instead of reopening the root path per image.
- Clarified the `README.md` CI checker summary to match what `check_readme.py`
  checks (Action inputs, MCP tools, binaries, and plugin/skill names).

## 0.1.3 — 2026-11-23

- Improved the skill's writing guidance (`references/page.md`), verification
  pass (`references/verify.md`), and checklist (`references/checklist.md`)
  so generated READMEs use natural, human language instead of cramped or
  robotic phrasing.
- Smoothed out the skill's own descriptions and rewrote `README.md` using
  the updated writing rules.

## 0.1.2 — 2026-11-23

- The guide's Codex update is one command, `codex plugin marketplace
  upgrade`, which also updates the installed plugin. 0.1.1 asked for
  `codex plugin add` again afterward, which is not needed.

## 0.1.1 — 2026-11-23

- The README opens with the prompt to type and the agent's real first reply,
  instead of checker output, and follows the skill's own page order for an
  extension: install right after the example, then first use, then the
  rest. `docs/example-session.md` holds the whole reply.
- The guide says how to check the plugin loaded in Claude Code, Codex,
  Grok and Antigravity, how to try a change from a clone, and how to
  update, switch off and remove it, in one table with a row per agent.
- `discover.py` and `check_readme.py` report version 0.1.1.

## 0.1.0 — 2026-11-23

The first release.

- A skill for Claude Code, Codex, Antigravity, Grok and other agents that
  read Agent Skills, installable as a plugin or as a plain skill.
- Writes, reviews and updates READMEs for apps, command-line tools,
  services, libraries, extensions and automation, agreeing on the reader, the
  highlights, the plan and the exact draft with the owner before writing.
- `discover.py` reads a project and reports what it is and what a user
  meets, with path and line for every fact.
- `check_readme.py` checks a README or a draft: links, anchors, pictures,
  placeholders, example markers, Action inputs, tool and skill names,
  secrets, and the page's shape.
- A GitHub Action that runs the checker on pull requests, with a
  `use-config` input to ignore a contributor's settings file.
- Both scripts are safe to run on a repository you do not trust: they read
  only inside the root, never run its code, keep git from running anything
  the repository configures, hide secret-shaped values, and stay within
  limits on files, bytes and time.
