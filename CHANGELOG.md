# Changelog

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
