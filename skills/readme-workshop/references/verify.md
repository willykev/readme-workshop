# The verify pass

Before stop 4, check the draft sentence by sentence against the project.
This pass is where most pages get better: a reader who checks a finished
draft against the code catches what the writer, deep in the draft, did not.
If the host can start a fresh subagent with no memory of the drafting, use
one: give it the draft path, the scratch copy's path (not the project's),
the commands the person approved at stop 3 and the checks below, and ask
for the evidence table. It runs nothing else. Otherwise do it yourself as a separate step, after
the draft is finished, reading the files again rather than relying on
memory.

## The evidence table

List every sentence that states a fact: a command, flag, option, path,
file name, version, platform, number, default, behavior, permission or
network use. For each:

| # | Claim (README line) | Evidence | Status |
|---|---|---|---|
| 1 | `pipx install cookconv` (L18) | pyproject.toml:12 `[project.scripts] cookconv` | found |
| 2 | "Writes nothing unless you pass `-o`" (L44) | cli.py:88 writes only in `if args.output` | source-traced |
| 3 | "Opens in 80 ms" (L60) | none | cut |

Status is one of: **ran** (you ran it and saw it), **found** (the file says
so), **source-traced** (followed from the entry point to the effect),
**owner** (the owner said so at a stop), **unverified**, or **cut**.

## Checks that catch most errors

Readers and reviewers find the same few mistakes again and again. Check
each one on purpose:

1. **Universal words.** For every "any", "every", "all", "always", "only",
   "never", "no", "each" and every count ("four buttons", "one file",
   "nine languages"), search the code for the exceptions: types it skips,
   cases it rejects, a default action that is not a button, a database
   with sidecar files, a list the help screen leaves out. Narrow the
   sentence to what holds.
2. **Live or after a restart.** "Changes when you change X" must be checked
   against how X is read: a value read once at start (a constant, a
   setting loaded at launch) changes only after a restart.
3. **The version installed.** If the install block pins a release (a tag, a
   package version, `@v1`), every feature on the page must be in that
   release. Check the changelog's "Unreleased" section and the commits
   after the tag; describe what the reader will actually get, or install
   from the branch that has it and say so.
4. **Build and runtime dependencies.** Take them from the build files
   (`package.json`, `requirements`, `Cargo.toml`, CMake `find_package`,
   `Makefile` `pkg-config` calls, distribution package recipes, CI install
   steps), not from prose. Prose lists go stale.
5. **Numbers.** Every number traces to a file in the project or to a command
   you ran whose method is (or will be, in the change set) in the project.
   A measurement made with a throwaway script, or on the owner's own
   running copy, does not go on the page.
6. **Shell traps in examples.** Text with `!`, `$`, backticks or `*` inside
   double quotes, or a command that only works from a certain folder, or
   with state from an earlier step: run it as written in a fresh shell in
   the scratch copy, if it is one of the commands the person approved.
7. **Scope words.** "Made for", "only works on", "not supported": the code
   and docs may support more (or less) than the owner's own setup.
8. **Walk the install on a clean machine.** This is the check that decides
   most pages. Read each install block as a stranger on a fresh system (not
   the owner's, which already has the toolchain), step by step, in order:
   open each script it runs and note what that step needs (compilers,
   system libraries, a runtime version, a logged-in CLI, an account) and
   whether an earlier step installed it. A script that builds
   before the package manager installs its dependencies needs them listed
   first. Multi-step deployments need their order checked (set up,
   then deploy, then the step that needs the deploy's output). Run it in a
   throwaway container when one is available.
9. **Screenshots match the words.** Read how each screenshot or recording was
   made (its capture script and options). One captured with non-default
   settings (a different size, color, or mode) cannot illustrate the default
   behavior; caption it for what it shows, or place it where the page
   describes those settings.
10. **Read it aloud.** Read every sentence as if explaining the project to a
    colleague. Rewrite anything that sounds cramped, overly literal, or
    robotic (for example, compressed phrasing like "settles the reader" or
    "what a user meets"), and remove any internal workshop jargon ("decision
    card", "surfaces", "enabler") that leaked into the draft.

## Then

- Cut every claim with no evidence, or soften it to what the evidence
  supports ("reads the file you name" instead of "never touches your
  files", if writes exist elsewhere).
- Re-run every command in the draft that you have not run since the code
  last changed, in the scratch folder.
- Check names letter by letter against the source: command, package,
  options, environment variables, tool names, input names.
- Check every number against its source.
- Keep the table. Show the unverified rows at stop 4; the person can
  confirm or drop them. Do not put the table in the README.
