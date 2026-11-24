"""Fixture trees, copied to a temporary folder for each test run.

Fixture skills are stored as SKILL.md.in, so skill installers that look for
skills/*/SKILL.md anywhere in this repository do not offer them as skills.
The copy gives them their real name.
"""
import atexit
import shutil
import tempfile
from pathlib import Path


def materialize(src):
    dst = Path(tempfile.mkdtemp(prefix="rw-fixtures-")) / Path(src).name
    shutil.copytree(src, dst, symlinks=True)
    for p in dst.rglob("SKILL.md.in"):
        p.rename(p.with_name("SKILL.md"))
    atexit.register(shutil.rmtree, dst.parent, True)
    return dst
