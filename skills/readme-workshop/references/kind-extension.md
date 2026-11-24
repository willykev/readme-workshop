# Extensions: skills, plugins, MCP servers, editor and browser extensions

The reader is an **enabler**: someone switching it on inside a host they
already use. They must decide whether it works in their host, what access
it gets, when it acts, and what it changes. A screenshot rarely answers any
of that.

## Decision card

- Hosts it works in, with versions (Claude Code, Codex, other agents; VS
  Code; a browser; a desktop shell), and the install command
  for each.
- What triggers it: a slash command, a phrase that makes an agent load a
  skill, an event (a hook), a key, a page the user visits.
- What it does then: the files it reads or writes, the commands it runs,
  the tools it exposes, what it shows.
- Access and permissions: tools allowed, network calls, browser
  permissions, secrets it needs.
- How to turn it off or remove it; anything it leaves behind.

## Where to look

| Sub-kind | Files |
|---|---|
| Agent skill | `SKILL.md` (frontmatter `name`, `description`; the body's steps), `references/`, `scripts/` |
| Agent plugin | `.claude-plugin/plugin.json`, root `plugin.json`, `marketplace.json`; `commands/`, `agents/`, `hooks/hooks.json`, `skills/`, `.mcp.json` |
| MCP server | Tool, resource and prompt registrations (`server.tool(...)`, `@mcp.tool`, `registerTool`) with their names, descriptions and input schemas; transport (stdio, HTTP); environment variables |
| Editor extension | `package.json` `contributes` (commands, settings, keybindings), `activationEvents`, `engines.vscode` |
| Browser extension | `manifest.json` (`permissions`, `host_permissions`, `content_scripts`, `action`) |
| Desktop shell plugin | The plugin manifest, the config lines it reads, the version of the host it targets |

## Show it working

Something real from the host:

- **A skill or plugin:** the request a user types and what the agent does
  with it, taken from a real session in the host (an excerpt of the
  transcript, trimmed but not reworded), or the command and the files it
  produced.
- **An MCP server:** a table of its tools (name, what it does, key inputs),
  checked against the registrations, plus one real call and its result.
- **An editor or browser extension:** a picture of it in the host, made with
  sample content (see [pictures](pictures.md)), or the command palette
  entry and its effect.

Never write a transcript by hand and present it as a session. If no real
run is possible at stop 3, show the trigger and the expected effect in
words, marked as such.

## Page

1. Name and pitch: the host and the job ("A Claude Code plugin that …",
   "An MCP server that lets agents …"); name every host it works in
2. Link row
3. Show it working inside the host by about line 20
4. Install where the user already is, within about 30 lines (and how to
   install from a local checkout, for someone trying a change): store links
   per browser or editor, in-host commands for agent plugins, one
   `mcpServers` block for an MCP server; alternatives in a collapsed
   `<details>` block. Requirements with versions next to it (host version,
   runtime). How to check it loaded.
5. One realistic invocation (a slash command with a real argument, a
   prompt, a key) and then, as numbered steps, what happens; within about
   60 lines
6. Features, commands or tools: a table with a when-it-applies or default
   column
7. What it touches: files and configs it writes (with the manual
   equivalent), what leaves the machine, telemetry and its opt-out, any
   option that runs arbitrary code
8. Scope and support: hosts and versions supported, what is not planned
9. How to update it and how to switch it off
10. More

Clear extension pages run 80 to 200 lines, with the first picture or
output within about 20 lines and the install step within about 30. Few show
real output as text or mention data and privacy; for agent plugins and MCP
servers, both should be on every page. Aim for 400 to 1,000 words; per-client setup and long catalogs go in the guide or a collapsed
block.

For an agent plugin or MCP server with no interface, the proof is the
visible output in a text block, or a first prompt and what the host did
with it.

## Pitfalls

- Install commands copied from another host or an old version of the
  host's command line. Check each against the host's `--help`.
- Tool or command names in the README that differ from the registrations
  (the checker compares them where it can).
- Not saying what it can access. Readers of agent extensions look for this
  first.
- A skill name in the install command that differs from `SKILL.md`.
