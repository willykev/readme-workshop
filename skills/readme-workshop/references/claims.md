# Claims: performance, data, limits

Contents: [Performance](#performance) · [Data and access](#data-and-access) ·
[Limits](#limits) · [Comparisons](#comparisons)

## Performance

Most READMEs claim speed with adjectives and give no measured start time or
memory figure. One honest measurement sets a project apart. A believable claim has:

- **A number with a unit**, never an adjective.
- **What was measured**: the action and the size of the data ("a 10,000-line
  file", "5,000 items").
- **On what**: machine, system and versions, the project's version.
- **How**: the command or script, kept in the project (`bin/benchmark`)
  so anyone can rerun it.
- **Where it stops holding**, if it does.
- **Comparisons only when measured the same way on the same machine**, with
  both commands shown.

Leave out a number that changes between runs unless several runs agree
(six or more for anything frame- or timing-sensitive), and a number
measured in conditions nobody runs in. Say what a timing includes. A
generated data set of ten thousand items is quick to make and gives the
claims people believe.

Write three or four facts as a short list, then one line: "Measured on
[machine] running [system], NAME [version], with `bin/benchmark`."

A statement about how it works can stand in for a number when it implies a
guarantee: "reads the file once and never writes to it", "no background
process".

Never run a benchmark the owner did not agree to at stop 3, and never
present an estimate as a measurement. A number goes on the page only when
the command that produced it is in the project, or is added in the change
set at stop 4 (`bin/benchmark`, a test that prints the figure): a reader
must be able to rerun it. A measurement of the owner's own running copy, or
one made with a script you threw away, stays out.

## Data and access

Four to six lines that answer, with facts from the code:

- Where it keeps things (paths), in what format.
- How to back them up and move them.
- Every time it uses the network, what it sends, and how to turn it off.
  Search the code for HTTP clients, sockets, update checks, analytics and
  crash reporters; the scanner lists `signals.network` and
  `signals.telemetry` with lines.
- What access it gets: permissions, tools, scopes, files outside its folder.
- What it deliberately does not do.

State absolutes flatly ("No account. Nothing leaves your computer.") only
when the code backs them: a single update check makes "never connects"
false. Labels without facts ("privacy-first", "secure") are not believed.

## Limits

Say what it does not do and the way around it, if there is one. It reads as competence and saves a
disappointed install. Take limits from the code (unsupported platforms,
size caps, missing formats), from the issue templates and the changelog,
and from the owner at stop 1.

## Comparisons

Do not compare with other projects unless the owner asks for it, and then
only with a measurement made the same way on the same machine, or a
feature table the owner has checked. Never describe this project as "X
for Y" or "like X but".
