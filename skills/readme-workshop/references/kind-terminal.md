# Command-line tools and terminal interfaces

The reader is an **installer** who works in a terminal: does it install
with my package manager, what does the first command print, and can I
script it?

## Decision card

- Install routes that exist (package managers, release binaries) and the
  command name (state any mismatch with the package name).
- Supported systems, shells and runtime versions.
- The first command worth running and its real output.
- Output formats for scripts (`--json`, exit codes), and config files.
- What it reads and writes; network use.

## Where to look

- The argument parser: argparse, click, typer, clap (derive or builder),
  cobra, urfave/cli, commander, yargs, oclif. Subcommands, options, defaults
  and help strings are the surface.
- Entry points in the manifest (`[project.scripts]`, `bin`, `[[bin]]`,
  `cmd/*/main.go`).
- Shell completions, man pages, a `--help` snapshot in tests.
- Config file format and location; environment variables read.
- Tests that run the command end to end: they show real invocations.

## Show it working

A real command and its real output, as text in a code block, near the
top. Text is copyable, searchable and readable at any width. Use a short
recording (see [pictures](pictures.md)) only when the output moves (a
progress display, an interactive interface).

Run the command in a scratch folder with sample input. Keep a copy of the
output in the project (for example `examples/` or `docs/`) and put an
example marker above the block so the checker keeps them equal:

````markdown
<!-- matches: examples/scale-output.txt -->
```text
Pancakes (serves 6)
  375 g flour
  ...
```
````

## Page

1. Name and pitch
2. Link row
3. A real run (command and output), or a recording for an interactive tool
4. Features (4 to 7), or skip them for a one-job tool
5. Install
6. First use: the first command, then 3 to 5 tasks, each a command and its
   output
7. Configuration, if there is a config file (snippet and up to 8 options)
8. Scripting: `--json`, exit codes, in a few lines
9. Performance, if measured (command-line readers expect the method)
10. More

Targets: 400 to 800 words; strong small tools stay well under that.

## Pitfalls

- `$ ` prompts in blocks meant to be copied.
- An invented or edited output block that no longer matches the tool.
- Listing every flag: the full list belongs in the guide or `--help`.
- Benchmarks with no machine, data size or command.
- A different binary name in the README than in the manifest.
