# Apps with a window

Desktop, web and mobile apps that people use through an interface. The
reader is an **installer**: will it run on my system, what will I see in
the first minute, and where do my things go?

## Decision card

- Systems and versions it runs on (desktop environment,
  browser, OS version), and architectures.
- The install route and what appears afterward (launcher entry, URL).
- The first thing a new user makes or does, and what it looks like.
- Where data lives, in what format, and whether anything leaves the
  machine (accounts, sync, telemetry, update checks).
- What it does not do that people may expect.

## Where to look

- The main window and its views (SwiftUI, XAML, QML, GTK builder files,
  React or Vue routes); toolbars and menus; actions and their shortcuts.
- Settings: what a user can change, and the defaults.
- The `.desktop` entry, app manifest, `Info.plist`, `AndroidManifest.xml`:
  name, category, permissions.
- Sample data in `examples/`, fixtures used by end-to-end tests: these are
  the best content for pictures.
- Storage: database files, config paths, `QStandardPaths`,
  `app.getPath`, `localStorage`, IndexedDB.
- Any option that draws a picture by itself (`--screenshot`, a headless
  render, a storybook): it decides how pictures can be made.

## Show it working

A short loop of the action that explains the pitch, or a still of a
finished result when the result is what a visitor needs to inspect. Then
three to five feature pictures in the first-use section, each tied to a
heading. Never a settings page. See [pictures](pictures.md) for how to make
them from a script with sample content and nothing personal.

If the app cannot draw itself and there is no way to capture it at stop 3,
say so, propose what to add (a `--screenshot` option or a capture script),
and leave a marked gap rather than a fake.

## Page

1. Name and pitch (with the platform)
2. Link row
3. Hero picture
4. Features (4 to 7)
5. Install (requirements line, one block, what appears next, update, remove)
6. First use: the first step, then 3 to 5 captioned blocks with pictures,
   then a key table of 10 to 12 rows
7. Commands, if it has a command line
8. Performance, if measured
9. Your data
10. More

Targets: 500 to 800 words, 120 to 180 lines, 4 to 6 pictures. A tool with
one idea needs fewer of everything.

## Pitfalls

- Writing about the toolkit instead of the result ("built with Qt 6").
- Showing an empty window, or a help page as the hero.
- A 1920-pixel screenshot that GitHub shrinks until nothing reads.
- Theme or font settings of the machine that drew the pictures leaking in.
- Claiming sync, export or plugins that are half built: trace each to a
  working path.
