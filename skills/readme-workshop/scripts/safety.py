"""What the scripts never open and never print, and how they open everything else.

Shared by discover.py, check_readme.py and formats.py. Standard library only.

- is_secret_path: files and folders that hold credentials. Neither script
  opens them, whatever links or names them.
- redact, sanitize: secret-shaped values and URL passwords are replaced, and
  control characters escaped, before anything reaches output.
- Tree: a project folder pinned for a scan, and the one way the scripts
  read files in it: confined to the folder, never a secrets file, never
  through a symlink, a bounded read of regular files only.
- ArgumentParser: argparse whose error messages are sanitized too.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import fnmatch
import os
import re
import stat
import sys

# File names that hold credentials or keys.
SECRET_NAMES = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*",
    "*credentials*", "*secret*", ".netrc", ".npmrc", ".pypirc", ".pgpass", ".htpasswd", ".git-credentials",
    "kubeconfig", "*.keystore", "*.jks", "*.kdbx", "*.tfvars", "*.tfvars.json", "*.tfstate", "*.tfstate.*",
    "terraform.tfstate*",
)
# Folders that hold credentials (or, for .git, remote URLs that may carry them): nothing below one is opened.
SECRET_DIRS = {"secret", "secrets", ".secrets", "credentials", ".credentials", ".ssh", ".gnupg", ".aws", ".kube",
               ".docker", ".git"}
# Samples a project documents for its users to copy.
SAMPLE_NAMES = {".env.example", ".env.sample"}


def is_secret_path(rel):
    """True for a path (relative, / or \\ separated) that is, or lies in, a secrets file or folder."""
    parts = [p.lower() for p in re.split(r"[\\/]+", str(rel)) if p not in ("", ".")]
    if not parts:
        return False
    if any(p in SECRET_DIRS for p in parts):
        return True
    name = parts[-1]
    return name not in SAMPLE_NAMES and any(fnmatch.fnmatchcase(name, glob) for glob in SECRET_NAMES)


# Secret shapes: label, pattern, characters kept when redacting, and a test that a
# match is a real-looking value rather than a documented sample (used by RW013).
SECRETS = (
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), 4, lambda v: not v.endswith("EXAMPLE")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}"), 4, lambda v: len(set(v[4:])) >= 8),
    ("GitHub token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}"), 11, lambda v: len(set(v[11:])) >= 8),
    ("API key", re.compile(r"(?<![\w-])sk-[A-Za-z0-9_-]{20,}"), 3,
     lambda v: re.search(r"\d", v[3:]) and re.search(r"[A-Za-z]", v[3:]) and len(set(v[3:])) >= 10),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"), 5, lambda v: re.search(r"\d", v)),
    ("Slack token", re.compile(r"\bxapp-[A-Za-z0-9-]{10,}"), 5, lambda v: re.search(r"\d", v)),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), 3,
     lambda v: not v.endswith("SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")),
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
# A key block, to its END line or, when that is missing, to the end of the text.
_KEY_BLOCK_RE = re.compile(r"(-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----).*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)",
                           re.S)
# user:password@ in a URL, the user name possibly empty.
_URL_PASSWORD_RE = re.compile(r"(?<=://)[^/\s@:]*:[^/\s@]*@")
_URL_USERINFO_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*://)[^/@]*@")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")  # every control character but tab
_CONTROL_NOT_NEWLINE_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _redact_text(text):
    for _label, rx, keep, _real in SECRETS:
        text = rx.sub(lambda m, k=keep: m.group(0)[:k] + "****", text)
    text = _KEY_BLOCK_RE.sub(lambda m: m.group(1) + "****", text)
    return _URL_PASSWORD_RE.sub("****@", text)


def _escape(ch):
    return {"\n": "\\n", "\r": "\\r"}.get(ch, "\\x%02x" % ord(ch))


def sanitize(value, newlines=True, escape=True):
    """Redact secret-shaped values in a string, list or dict (keys too), and escape control characters.

    newlines=False also escapes line breaks, for plain-text output where a
    value must stay on its line. escape=False only redacts.
    """
    if isinstance(value, str):
        value = _redact_text(value)
        if escape:
            value = (_CONTROL_NOT_NEWLINE_RE if newlines else _CONTROL_RE).sub(lambda m: _escape(m.group(0)), value)
        return value
    if isinstance(value, (list, tuple)):
        return [sanitize(v, newlines, escape) for v in value]
    if isinstance(value, dict):
        return {sanitize(k, newlines, escape) if isinstance(k, str) else k: sanitize(v, newlines, escape)
                for k, v in value.items()}
    return value


def redact(value):
    """Secret-shaped values replaced with a stub; nothing else changed."""
    return sanitize(value, escape=False)


def strip_userinfo(url):
    """A URL without its user:password@ part."""
    return _URL_USERINFO_RE.sub(r"\1", url) if isinstance(url, str) else url


# ---------------------------------------------------------------- reading files

_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
DIR_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_DIRECTORY", 0)
# Folders can be opened one below the other and listed by descriptor (POSIX).
WALK_BY_FD = (os.open in os.supports_dir_fd and os.scandir in os.supports_fd and hasattr(os, "O_DIRECTORY")
              and hasattr(os, "O_NOFOLLOW"))
_NAME_SURROGATE = 0x20000000  # the reparse tags of Windows symlinks and junctions carry this bit


def _parts(rel):
    parts = [p for p in re.split(r"[\\/]+", str(rel)) if p not in ("", ".")]
    if ".." in parts:
        raise OSError("path leads out of the root: %s" % rel)
    return parts


def _same(a, b):
    return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


def _is_link(st):
    """A symlink, or on Windows a junction or any other reparse point that names another path."""
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_reparse_tag", 0) & _NAME_SURROGATE)


class Tree:
    """A project folder, pinned when it is opened, and the one way the scripts read files in it.

    Every read names a path relative to the folder. It is refused when that
    path, or the path it resolves to, leads outside the folder or is a secrets
    file or folder (is_secret_path). Otherwise the file is opened from the
    pinned folder down, following no symlink, and read only if it is a regular
    file. On POSIX the folder is held open, so the whole scan reads the folder
    it started in even if its name is moved; elsewhere each opened file is
    checked against the path it was validated as, and the folder against the
    identity it had when pinned.
    """

    def __init__(self, path):
        self.abs = os.path.realpath(path)
        if not os.path.isdir(self.abs):
            raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), str(path))
        self.fd = None
        if WALK_BY_FD:
            self.fd = os.open(self.abs, os.O_RDONLY | os.O_DIRECTORY)
            st = os.fstat(self.fd)
        else:
            st = os.stat(self.abs)
        self.ident = (st.st_dev, st.st_ino)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:  # noqa: BLE001 (interpreter shutdown)
            pass

    # Paths ---------------------------------------------------------------

    def inside(self, real):
        """True for an absolute, resolved path at or below the folder."""
        return real == self.abs or real.startswith(self.abs.rstrip(os.sep) + os.sep)

    def resolve(self, rel):
        """The absolute path rel leads to, symlinks resolved."""
        return os.path.realpath(os.path.join(self.abs, *_parts(rel)))

    def refusal(self, rel, follow=True, git_data=False):
        """Why rel is never read ("outside" or "secret"), or None.

        follow: rel may pass through symlinks that stay inside the folder, and
        the path they lead to is checked too. git_data: rel lies in .git and is
        read only to check git's own data; .git itself is then allowed, every
        other secrets rule still applies.
        """
        return self._target(rel, follow, git_data)[0]

    def _target(self, rel, follow, git_data):
        """(refusal, the path to open relative to the folder), the path resolved once."""
        try:
            parts = _parts(rel)
            real = self.resolve(rel) if follow else os.path.join(self.abs, *parts)
        except (OSError, ValueError):
            return "outside", None
        if not self.inside(real):
            return "outside", None
        target = os.path.relpath(real, self.abs) if follow else "/".join(parts)
        names = {"/".join(parts), target}
        if git_data:
            if parts[:1] != [".git"]:
                return "secret", None
            names = {re.sub(r"^\.git(?:[\\/]|$)", "", n) for n in names}
        return ("secret", None) if any(is_secret_path(n) for n in names) else (None, target)

    # Opening -------------------------------------------------------------

    def open(self, rel, flags=_READ_FLAGS):
        """File descriptor for rel, a path with no symlink in it; raises OSError."""
        parts = _parts(rel)
        if WALK_BY_FD:
            fd = os.dup(self.fd)
            try:
                for part in parts[:-1]:
                    child = os.open(part, DIR_FLAGS, dir_fd=fd)
                    os.close(fd)
                    fd = child
                # "." is a new opening of the folder, so it does not share a read position with self.fd.
                return os.open(parts[-1] if parts else ".", flags | os.O_NOFOLLOW, dir_fd=fd)
            finally:
                os.close(fd)
        full = os.path.join(self.abs, *parts)
        self._check_path(parts)
        fd = os.open(full, flags)
        try:
            # Opened by name: whatever happened on the way, the file must be the one the
            # validated path names now, reached without a link, below the pinned folder.
            if not _same(os.fstat(fd), os.stat(full)):
                raise OSError("%s changed while it was opened" % rel)
            self._check_path(parts)
        except BaseException:
            os.close(fd)
            raise
        return fd

    def _check_path(self, parts):
        """Raise OSError unless the folder is the pinned one and no part of the path below it is a link."""
        st = os.lstat(self.abs)
        if _is_link(st) or (st.st_dev, st.st_ino) != self.ident:
            raise OSError("the root folder was replaced")
        for k in range(1, len(parts) + 1):
            if _is_link(os.lstat(os.path.join(self.abs, *parts[:k]))):
                raise OSError("a link lies on the path %s" % "/".join(parts[:k]))

    @contextlib.contextmanager
    def scandir(self, rel):
        """An os.scandir iterator over a folder below the root, opened as open() opens files."""
        if WALK_BY_FD:
            fd = self.open(rel, DIR_FLAGS)
            try:
                with os.scandir(fd) as it:
                    yield it
            finally:
                os.close(fd)
        else:
            parts = _parts(rel)
            self._check_path(parts)
            with os.scandir(os.path.join(self.abs, *parts)) as it:
                yield it

    # Reading -------------------------------------------------------------

    def read_bytes(self, rel, limit, follow=True, git_data=False):
        """Up to limit bytes of the regular file rel, or None if it is refused, not one, or unreadable."""
        why, target = self._target(rel, follow, git_data)
        if why:
            return None
        try:
            fd = self.open(target)
        except (OSError, ValueError):
            return None
        return _read_fd(fd, limit)

    def read_text(self, rel, limit, follow=True, git_data=False):
        """Text of a whole regular file of at most limit bytes (see read_bytes), else None."""
        return decode_text(self.read_bytes(rel, limit + 1, follow, git_data), limit)


def _read_fd(fd, limit):
    """Up to limit bytes from an open file, which must be a regular file; closes it."""
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        chunks, size = [], 0
        while size < limit:
            chunk = os.read(fd, min(limit - size, 1 << 20))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        return b"".join(chunks)
    except OSError:
        return None
    finally:
        os.close(fd)


def decode_text(data, limit):
    """Text of bytes read with a limit of limit + 1: None if they are None or over the limit."""
    if data is None or len(data) > limit:
        return None
    return data.decode("utf-8", "replace").lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")


def read_regular(path, limit, root=None):
    """Up to limit bytes of a regular file, or None if it is not one or cannot be read.

    With root, path is relative to it and read through a Tree (so secrets files
    are refused too); without, the path is opened as given, not following a
    final symlink. Pipes and devices are never read.
    """
    if root is not None:
        try:
            with Tree(root) as tree:
                return tree.read_bytes(path, limit, follow=False)
        except OSError:
            return None
    try:
        fd = os.open(path, _READ_FLAGS)
    except (OSError, ValueError):
        return None
    return _read_fd(fd, limit)


def read_text(path, limit, root=None):
    """Text of a whole regular file of at most limit bytes (BOM dropped, newlines as \\n), else None."""
    return decode_text(read_regular(path, limit + 1, root), limit)


# ---------------------------------------------------------------- command lines

class ArgumentParser(argparse.ArgumentParser):
    """argparse, with its error messages redacted and escaped like every other output."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, "%s: error: %s\n" % (self.prog, sanitize(message, newlines=False)))
