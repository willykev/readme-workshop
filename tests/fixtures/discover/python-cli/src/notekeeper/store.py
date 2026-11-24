import os
import sqlite3


def connect(path=None):
    path = path or os.environ.get("NOTEKEEPER_HOME", "~/.notes.db")
    return sqlite3.connect(os.path.expanduser(path))
