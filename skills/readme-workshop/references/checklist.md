# Checklist

Use it in review mode, and before stop 4 on your own draft. Run the
checker first:

```sh
python3 -I -B scripts/check_readme.py --root PROJECT_DIR --format text
```

Errors are defects; warnings are worth a look; manual items need a person
or a real run.

## The first screen (about 25 lines on GitHub)

- [ ] The name, what it is in one sentence, and a picture or real example,
      with nothing above them but the title.
- [ ] A stranger could say what it is and who it is for from the pitch
      alone.
- [ ] The pitch names a plain category and what it works with; no
      adjective the next line does not prove; no other product named.
- [ ] At most two badges near the top, each one a user acts on.

## Getting it

- [ ] The install section starts within about 50 lines.
- [ ] One requirements line; one block that runs as written; no
      placeholders in it.
- [ ] The block was run on a clean system, or is marked untested.
- [ ] Package and command names match the manifests; a mismatch is called
      out.
- [ ] What happens next is said; required steps after install are
      numbered, with how to undo them.
- [ ] Update and remove in one line each.

## Showing it

- [ ] What it looks like working comes from a real run: a picture drawn
      from sample content, or a real input and its real output.
- [ ] Every code block with output has an example marker, or was re-run
      for this draft.
- [ ] Pictures (if any): 4 to 6 for an app, each captioned, each showing
      one thing in use, readable at 600 and 900 pixels wide, nothing
      personal in them, made by a script in the project.
- [ ] Alt text says what the picture shows.

## Content

- [ ] 4 to 7 features, each saying what the user can do, most distinctive
      first; none restates an adjective.
- [ ] The first-use section takes the reader from nothing to a first
      result.
- [ ] Every performance claim is a number with a machine and a method.
- [ ] The data or access section names paths, formats, every network use,
      and the access granted.
- [ ] At least one honest limit, if the project has one.
- [ ] Nothing explains how it was built, what was considered, or what is
      planned.
- [ ] Every sentence reads like natural, idiomatic English you would say to
      a colleague — no cramped shorthand, robotic phrasing, or internal
      workshop jargon.
- [ ] For an extension: install per host, the trigger, what it can access,
      how to turn it off. If you try the install, do it in a throwaway
      profile of the host (a separate config folder), never the person's
      own. For an Action: pinned snippet, inputs and outputs
      that match `action.yml`, permissions.

## Truth

- [ ] Every factual sentence is on the [verify](verify.md) table as ran,
      found, source-traced or owner; nothing unverified is stated as fact.
- [ ] Every link and anchor resolves; every picture exists.
- [ ] No secrets, tokens, real names or home paths anywhere.

## Around the README

- [ ] Every feature in the README has a section in the guide, if there is
      one.
- [ ] Suggested to the owner: About line (the pitch's first sentence),
      topics, a social preview image (1280 by 640), a release whose
      download file names do not change between versions.
