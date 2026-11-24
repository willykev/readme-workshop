# An example session

The first exchange of a real Claude Code session (Claude Code 2.1, with
readme-workshop 0.1.0 installed), in a small sample project: cookconv, a
command-line tool and Python library that scales plain-text recipes and
converts their units. The project had no README. The reply is as the agent
wrote it.

**Prompt:** Use readme-workshop to write a README for this project.

**Reply:**

> **What I found (stop 1 of 4)**
>
> cookconv scales plain-text recipes to a different number of servings and converts their units between US and metric. You can use it as a command-line tool or as a Python library.
>
> - **For:** people who keep recipes as text files and would run the command, and Python developers who would import `parse`, `scale` and `convert` (`cookconv/__init__.py:4`).
> - **Install:** `pipx install cookconv`, which gives you the `cookconv` command (`pyproject.toml:13`). No dependencies are needed beyond the standard library.
> - **First result:** `cookconv scale examples/pancakes.txt --serves 6` prints the recipe for six. `examples/pancakes-6.txt` and `examples/pancakes-6-metric.txt` look like the saved output, with and without `--to metric`. I haven't run anything yet.
> - **Runs on:** Python 3.10 or later (`pyproject.toml:9`). Nothing in the code is tied to one operating system.
> - **Your files:** it only reads the recipe you name. It writes a file only when you pass `-o` (`cli.py:18`, `cli.py:26`), and it makes no network calls.
> - **Recipe format:** the first line must be a title ending in `(serves N)` (`recipe.py:32`). After that, each line that starts with a number is an ingredient and every other line is a step.
> - **Couldn't tell:** whether it's published on PyPI (there's no release workflow or repository URL), and which reader the page should address first. There's no existing README, changelog or test suite to go on.
>
> Is this right? Correct anything that isn't, and answer these:
> 1. Is cookconv on PyPI? If not, I'll show how to install it from a clone with `pipx install .`.
> 2. Which reader should the page address first, cooks or developers? If you're not sure, I'll lead with cooks and add a short "From Python" section.

After the owner answers, the skill goes on to stops 2 to 4, which the
[guide](guide.md) describes, and writes nothing until the draft at stop 4
is accepted.
