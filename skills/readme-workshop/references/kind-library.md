# Libraries, SDKs and frameworks

The reader is an **integrator**: does it fit my language, runtime and
stack, what does the first call look like, and what will it cost me in
dependencies, size and maintenance?

## Decision card

- Package name and the install command for its registry.
- Language and runtime versions; platforms; ESM/CommonJS, async/sync,
  typed or not.
- The smallest working program that does the main job, and its real output.
- Dependencies it pulls in, and size where it matters (front-end bundles).
- Stability: version, whether the API is stable, how breaking changes are
  handled.
- License.

## Where to look

- Public exports: `__all__` and `__init__.py`, `index.ts`/`exports` in
  `package.json`, `pub` items in `lib.rs`, exported Go identifiers, public
  classes. Names starting with `_` or marked internal are not the API.
- Type signatures and doc comments of the exported items.
- `examples/` and tests that read like usage: they show the intended calls.
- The changelog: what was announced, what broke.

## Show it working

The smallest program a reader could paste that does the main job, then what
it prints, both from a real run:

````markdown
```python
from cookconv import scale

print(scale("2 cups flour", serves=6, base=4))
```

```text
3 cups flour
```
````

Prefer an example file the project already runs in its tests or CI, and put
an example marker above the block so the page and the file cannot drift. If
the example needs credentials or a service, say what and show a local
alternative when one exists.

## Page

1. Name and pitch: one sentence naming the language or ecosystem and a
   category noun (about 12 words)
2. Link row (docs or API reference first, if one exists)
3. Install: one line in the ecosystem's own form (`pip install`, `npm
   install`, `cargo add`, `go get`), one channel, no per-system section
4. The smallest working example and its result
5. Features (4 to 7), each a capability with a tiny inline example where it
   helps; or skip them when the examples say it all
6. Three to six task sections, each one sentence and one block, reusing the
   same object or data
7. Compatibility in one place: minimum language version, platforms,
   browser or no-std support, dependencies, size
8. Where it stops: scope, and when to use something else, as a rule ("for
   application code; in a library, return your own error type")
9. More: the API reference (say what is there), the guide, the changelog,
   the license

Install usually comes before the example, since it is one line. When the
core idea fits in about 15 lines, the example may come first.

Reach the first code block within about 35 lines. Link the docs site rather
than carrying an API table on the page. Aim for 300 to 1,000 words.
With five or fewer public functions, a signature heading each, with what it
returns, can replace a reference link.

Every example that computes something states its result: a `//=>` comment
in JavaScript, a `>>>` session in Python, `// Output:` in Go, `assert_eq!`
or console output in Rust. Few library READMEs do, so this
alone sets a page apart. The first example runs as
pasted: imports included, one realistic task, about 15 lines.

A picture only when the output is visual (terminal styling, logs,
progress); otherwise the output block is the picture.

## Pitfalls

- Documenting the internals or the class hierarchy instead of tasks.
- An example that does not run: wrong import path, a renamed function, a
  missing `await`.
- Claiming zero dependencies when the manifest lists some.
- Benchmarks against other libraries without the method and versions.
