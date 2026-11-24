# Install sections

Contents: [Shape](#shape) · [Choosing the lead route](#choosing-the-lead-route) ·
[Patterns by channel](#patterns-by-channel) · [After installing](#after-installing) ·
[Update and remove](#update-and-remove) · [Checks](#checks)

## Shape

```markdown
## Install

cookconv needs Python 3.10 or later, on Linux, macOS or Windows.

    pipx install cookconv

Then run `cookconv --version` to check it worked, and see [your first recipe](#scale-your-first-recipe).

Other ways: `uv tool install cookconv`, or from source:

    git clone https://github.com/OWNER/cookconv && cd cookconv && pipx install .

Update with `pipx upgrade cookconv`; remove with `pipx uninstall cookconv`.
```

One requirements line, one block that runs as written, what to do next,
alternatives in five lines or fewer each, then update and remove. Every
route in full goes in the guide.

The requirements line also says how to get anything a newcomer may not
have: the toolchain (rustup for Rust, a virtual environment or `pipx` for a
Python tool, the Node version from `.nvmrc` or `.tool-versions`), a logged-in
host for an extension, an account for a cloud service. A platform the
project does not support is stated here, not only under limits. If a route
builds a binary, either install it onto the `PATH` or use the same full path
in every later example.

## Choosing the lead route

Lead with the route that is (1) found in the project (a manifest, a
release workflow, a package recipe), (2) one command for most readers, and
(3) easy to update and remove. Ask at stop 1 when several fit. Never lead
with a route the project does not ship: a `pip install` for a package not
on PyPI, a `brew install` with no formula, a Docker image nobody publishes.
If the only route is from source, say so and make the source route short.

## Patterns by channel

| Channel | Evidence in the project | Lead command | Notes |
|---|---|---|---|
| PyPI, a tool | `[project.scripts]` in `pyproject.toml`, a publish workflow | `pipx install NAME` or `uv tool install NAME` | Prefer an isolated tool install over `pip install` for commands |
| PyPI, a library | `pyproject.toml` with no scripts | `pip install NAME` (or `uv add NAME`) | State the supported Python versions |
| npm, a tool | `bin` in `package.json` | `npm install -g NAME`, or `npx NAME …` to try | Say the Node.js version from `engines` |
| npm, a library | `main`/`exports` | `npm install NAME` | Mention ESM/CommonJS if both or only one is supported |
| crates.io | `Cargo.toml` with `[[bin]]` or `src/main.rs` | `cargo install NAME` | A library: `cargo add NAME` |
| Go | `go.mod`, `cmd/NAME/main.go` | `go install MODULE/cmd/NAME@latest` | Library: `go get MODULE` |
| Arch Linux | `PKGBUILD`, `.SRCINFO` | `yay -S NAME` (AUR) or `sudo pacman -S NAME` (official) | Check the AUR name before publishing; a taken name means a different package name |
| Homebrew | a formula or tap in the tree or the docs | `brew install OWNER/TAP/NAME` | |
| Debian/Ubuntu | `debian/`, a `.deb` in releases | `sudo apt install ./NAME_VERSION_ARCH.deb` from a release | Prefer a stable `releases/latest/download/FILE` link |
| Flatpak, Snap | a manifest, a store listing | `flatpak install flathub ID` | |
| Windows | winget/scoop manifests | `winget install ID` | |
| Release assets | a release workflow that uploads files | A download link to `releases/latest/download/FILE` | Keep asset file names fixed across versions so the link stays right |
| Docker / compose | `Dockerfile`, `compose.yaml`, a published image | `docker compose up -d` from the repository, or `docker run … IMAGE` | Say the URL to open and the volume that holds the data |
| Agent plugin | `.claude-plugin/`, root `plugin.json` | One block per host: `claude plugin marketplace add OWNER/REPO` then `claude plugin install NAME@MARKET`; `codex plugin marketplace add OWNER/REPO` then `codex plugin add NAME@MARKET`; `agy plugin install TARGET`; `grok plugin install OWNER/REPO --trust` | Check each host's command against its `--help`; hosts change these |
| Agent skill | `skills/NAME/SKILL.md` | `gh skill install OWNER/REPO NAME --agent HOST` | Or copy the folder into the host's skills folder; name both |
| MCP server | an MCP SDK, a server entry point | The host's config snippet (JSON) with the command and arguments | Label it with the host and file it goes in |
| Editor extension | `engines.vscode`, a marketplace ID | `code --install-extension PUBLISHER.NAME` | Plus the marketplace link |
| Browser extension | `manifest.json` with `manifest_version` | The store link | And "load unpacked" for development, in the guide |
| GitHub Action | `action.yml` | A workflow snippet with `uses: OWNER/REPO@vMAJOR` | Pin to a release tag, never `@main` |
| From source | a build file | Clone, then the build in five lines or fewer | Dependencies as one package-manager line |

## After installing

Say what happens next, in one line: where the app appears, the command
that starts it, the URL to open (`http://localhost:8080`), the shell to
restart, the first command to run, or how to check it loaded in the host.

Number every step that is not optional:

```markdown
1. Add the hook to `.pre-commit-config.yaml` (snippet below).
2. Run `pre-commit install` once in the repository.
```

Say what each step changes on the system and how to undo it.

## Update and remove

One line each. Say what removal leaves behind (data, settings) and how to
remove that too. Almost no README says how to uninstall; it costs one
line and it is a sign of respect.

## Checks

- The lead block runs as written on a clean system. Run it in a scratch
  container or a throwaway home when you can; otherwise mark it
  `untested` at stop 4.
- The package name, the command name and the names in the block match the
  manifests (the checker warns on a command it cannot match).
- Download links point at files that the release actually produces, with
  the exact file names (compression included).
- Version requirements match the manifest (`requires-python`, `engines`,
  `rust-version`, `go` directive, minimum host version).
- Build dependencies come from the build files (`package.json`,
  `Cargo.toml`, CMake `find_package`, `Makefile` `pkg-config` calls,
  distribution package recipes, CI install steps), and the source build lists all of them before the
  build command, not just what the prose in CONTRIBUTING says.
- A block that installs a pinned release (a tag, a version) is paired with
  a page that describes that release: check the changelog's "Unreleased"
  section before describing a feature the pinned version lacks.
