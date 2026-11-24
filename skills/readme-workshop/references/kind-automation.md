# Automation: GitHub Actions, CI workflows and hooks

The reader is an **enabler** wiring it into a pipeline or a repository. They
need the snippet to paste, every input and output, what it changes, and
what it costs in permissions and time.

## Decision card

- How it is used: `uses: OWNER/REPO@vMAJOR` in a workflow; a
  `.pre-commit-config.yaml` entry; a reusable workflow call; a hook file.
- Inputs (required or not, defaults), outputs, and environment variables.
- Permissions it needs (`GITHUB_TOKEN` scopes, secrets) and what it writes
  (comments, commits, releases, files).
- Runners and systems it supports; the runtime (`node20`, `node24`,
  composite, Docker) and what that costs in start time.
- What a run reports: annotations, a summary, an exit status.

## Where to look

- `action.yml`: `name`, `description`, `inputs`, `outputs`, `runs.using`,
  composite `steps`, `branding`.
- Workflow files under `.github/workflows/` (including `workflow_call`).
- `.pre-commit-hooks.yaml`: `id`, `entry`, `language`, `files`, `args`.
- The action's own tests or example workflows: they show real usage.
- Release tags: they decide what to pin (`v1`, `v1.2.3`).

## Show it working

The snippet to paste, pinned to a released tag, then what the run shows
(the log lines, the annotation, the summary, the comment) from a real run.
Link a real workflow run where the project has one. The inputs table must
match `action.yml` exactly; the checker compares them.

```yaml
- uses: OWNER/check-links@v2
  with:
    paths: docs/
    fail-on: error
```

## Page

1. Name and pitch: "A GitHub Action that VERB OBJECT", "A pre-commit hook
   for TOOL", "Reusable workflows for JOB" (about 16 words). If it does
   several things, a numbered list of its steps. Never release notes or
   notices above that sentence.
2. Link row (badges: the Marketplace listing and CI at most)
3. Usage by about line 40, copyable as it stands: for an Action, a complete
   workflow file, the path to save it under and when it runs; for
   pre-commit, the entry with `rev:` pinned, then `pre-commit install`; for
   a reusable workflow, the `jobs:` block with `uses: …@vMAJOR`, `with:` and
   `secrets:`
4. How to try it before relying on it: a test repository, a manual
   `workflow_dispatch` run, or `uses: ./` from a checkout of this repository.
5. Permissions next to that first example: `permissions:` lines with a
   comment saying why, any repository setting with its menu path, and the
   error people get without it
6. What a run produces: a picture of the result (the pull request, comment
   or job summary it makes), or a console block of a failing then passing
   run
7. Inputs: every input with its default, as a table (name, description,
   default, required) or one commented YAML block; say "all inputs are
   optional" when true
8. Outputs: each with an example value, and one later step using
   `steps.ID.outputs.NAME`
9. Behavior as condition and result, including the quiet cases (nothing to
   do, already exists); for caches, what is stored and when it does not help
10. Further examples named by task, each one sentence and at most about ten
   lines
11. Pinning: `@vMAJOR` in short examples is what most readers expect; also
    show the full-commit-SHA form with the release in a comment
    (`uses: OWNER/REPO@<40-char sha> # v2.1.0`) and how to keep it updated
    with Dependabot, since a tag can be moved after you review it
12. More

Put the usage block within about the first 45 lines. Document outputs and
show real output as text: few automation READMEs do either. Aim for 400 to
1,100 words; the input table may push it past that, which is fine.

## Pitfalls

- `@main` or `@master` in the snippet (the checker warns).
- Inputs in the README that `action.yml` does not have, or required ones
  missing (the checker errors).
- Asking for `write` permissions without saying why.
- No word on what a failure looks like.
