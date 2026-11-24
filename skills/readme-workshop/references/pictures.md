# Pictures: screenshots, loops and recordings

Contents: [Which pictures](#which-pictures) · [What is in them](#what-is-in-them) ·
[How they are made](#how-they-are-made) · [Desktop apps](#desktop-apps) ·
[Web apps](#web-apps) · [Terminal](#terminal) · [Size](#size) ·
[Stills or motion](#stills-or-motion) · [On the page](#on-the-page)

Many READMEs show no picture of the product, or only one. A handful of
good pictures sets a project apart. The strong pattern: one picture on the first screen, then three to five tied to
features further down.

## Which pictures

- **The hero** opens on the whole interface in use and demonstrates the
  main interaction.
- **Three to five features**, chosen by asking what someone would show a
  friend. Each shows one feature while it is used: a dialog open, a
  selection made, a result on screen.
- **One proof picture** when the project makes a claim a picture proves
  (follows the system theme: the same window in several themes side by
  side).
- **Not settings pages.** They show configuration, not the product working.

## What is in them

- Sample content that tells one small story (a weekend trip, a week of
  errands, an essay), reused in every picture so the page reads as one
  piece. Keep it in `examples/` so it ships and can be opened.
- Content about the subject, not about the app. A board of notes explaining
  shortcuts reads as a help page.
- Never the real desktop, real names, real files, real accounts or
  anything personal. Check what other programs in the frame reveal
  (a terminal's prompt, a system monitor, a file manager).
- The system's default theme for the main set, so the pictures match what a
  new user sees.

## How they are made

Pictures come from a script in the project (`bin/screenshots` or similar)
that anyone can rerun, never from a manual screen grab:

- **By the program, where it can.** An option that renders the window to a
  file (`--screenshot PATH`) with the state set by options (size, view,
  selection, theme, time) makes each picture one command. If the app lacks
  one, propose adding it at stop 3; it is usually small.
- **In a scratch home.** `HOME`, the data folder and the config folder
  point at a temporary directory holding a fresh copy of the sample, with
  the default theme. Nothing of the owner's can appear.
- **Cut off from the desktop.** No notifications, no single-instance
  handoff to a running copy, no network unless needed.
- **At a fixed time**, when the interface shows dates.
- **Checked before taken.** Where a picture depends on which window or
  item is active, the script asserts it first.
- **Left alone when nothing changed.** Rendering is rarely identical bit for
  bit. Compare each new picture with the existing one under a small
  tolerance (`magick compare -metric AE -fuzz 2% a.png b.png null:`) and
  replace only those that differ; when one changes and the look did not,
  find out why before keeping it.
- **Regenerated, never retouched.**

## Desktop apps

| Toolkit or system | Off-screen recipe |
|---|---|
| Electron | `BrowserWindow.capturePage()` with `show: false`, at a fixed window size |
| macOS | `screencapture -l WINDOW_ID`, with the app opened on sample data in a separate user account or a fresh `HOME` |
| Windows | A test account or VM, the app at a fixed size, and a capture via the app or PowerShell |
| Qt | `QT_QPA_PLATFORM=offscreen` and the app's own grab (`QWidget::grab`, `QQuickWindow::grabWindow`) |
| GTK 4 | `GDK_BACKEND=broadway`, or a widget snapshot (`gtk_widget_snapshot_child`) where the app can save its own picture |
| Other Linux apps | A virtual display (`Xvfb :99 -screen 0 1280x800x24`) or a headless compositor, then the app's own grab or a screen capture |

Desktop effects (a notification balloon, window management) need a real
or nested compositor; describe them in words if they cannot be captured
cleanly.

## Web apps

Start the app on seeded sample data in a scratch folder or container, then
capture with a headless browser at a fixed viewport:

```sh
npx playwright screenshot --viewport-size=1280,800 http://localhost:3000 screenshots/hero.png
```

Log in as a sample user, never a real one. Fix the date if the interface
shows it. A short scripted flow (Playwright) can produce the frames of a
loop.

## Terminal

Prefer text: a command and its output in a code block. When motion matters
(a progress display, an interactive interface), record a script, not a
person typing:

- `vhs demo.tape` (a scripted recording to GIF), or
- `asciinema rec -c "COMMAND"` then `agg demo.cast demo.gif`.

Use a clean prompt and a scratch folder, a fixed terminal size (about 100
by 30), and the default theme. Keep it under ten seconds.

## Size

GitHub shows a README at most about 900 pixels wide on a repository's front
page, and about 600 in a browser window tiled to half a screen, and scales
every picture down to fit. A 1920-pixel-wide window lands below half size
and its text becomes unreadable.

- Frame the hero in a window about 1100 to 1280 logical pixels wide; keep
  a 2x still for high-density screens.
- Draw feature pictures from a smaller window (800 to 960 logical pixels),
  zoomed in on the feature, so they still read at 600.
- Draw at the final size. Resizing afterward blurs flat color and can
  make the file several times larger.
- Keep stills under about 500 KB and loops under about 3 MB.
- Check every picture at 600 and 900 pixels wide before stop 4.

## Stills or motion

A loop for an action whose result unfolds (something following the
pointer, a list narrowing as someone types, a result appearing beside the
input); a still for a result someone will study, or a comparison.

- One action per loop, with its own caption that names the input and the
  visible result, so it still makes sense paused. Readers can stop
  animation, and some browsers do it for them.
- Hold the opening briefly and leave time to read the result before the
  repeat: about five to eight seconds in all.
- Draw loops from the program, frame by frame, rather than recording a
  screen: render successive states, then join them.

```sh
magick -delay 100 frames/open.png -delay 80 frames/typed.png \
       -delay 200 frames/result.png -layers Optimize -loop 0 screenshots/search.gif
ffmpeg -framerate 12 -i frames/%03d.png -vf "split[a][b];[a]palettegen[p];[b][p]paletteuse" screenshots/drag.gif
```

## On the page

- The hero has no caption; the pitch above it is the caption.
- Every other picture has a sentence directly above it saying what it shows
  and which key or command gets there.
- Alt text describes the picture literally ("The week view with three
  reminders due on Friday"), never "screenshot" or a file name.
- One picture per row at full width; two side by side only for a pair meant
  to be compared, and only if each reads at half width.
- Files live in `screenshots/` (or the project's existing folder) with names
  for what they show: `hero.gif`, `search.gif`, `themes.png`.
