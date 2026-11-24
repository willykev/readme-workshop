# The user guide

`docs/guide.md` is the manual: where someone goes to do one particular
thing once they have installed. The README gets them installed and through
the first minute; the guide holds everything else a user needs. Start from
[the guide template](../assets/guide.template.md).

## When to write one

Propose a guide at stop 3 when the full list of commands, keys, settings,
inputs or API calls would push the README far past its size, or when the
project already has scattered docs a user must assemble. A tool with one
job and a handful of options can live in the README alone.

## Rules

- Organized by task ("Set a due date", "Export a board", "Authenticate"),
  never by part of the window or module ("The details pane", "utils").
- Every feature the README names has a section here, and the README links
  to it instead of explaining twice. Check both ways.
- It holds the complete versions of what the README samples: every install
  route, every key, every command and option, every setting with its
  default, every path, every input and output.
- It has the sections a README has no room for: troubleshooting written as
  the symptom someone would search for ("The window does not open"),
  backup and restore, what it changes on the system and how to undo it,
  what it does not do.
- It leaves out how the project is built and why it was designed that way,
  unless the project's own rules say otherwise.
- Each section can be read on its own; a contents line at the top only
  when the guide runs past about 150 lines.

## For code with no window

- **Terminal:** one section per command with a real example and its output;
  then shared options, output formats, exit codes, configuration file,
  environment variables.
- **Library:** one section per task with a runnable example; then
  configuration, errors and how to handle them, compatibility, migration
  between major versions. Link the API reference for every signature.
- **Extension:** per host, install, check, configure, remove; every
  command, trigger or tool with its inputs; what it can access; how to
  debug it in the host.
- **Automation:** every input and output with defaults and examples;
  permissions; common setups; what a failure looks like and how to read it.
