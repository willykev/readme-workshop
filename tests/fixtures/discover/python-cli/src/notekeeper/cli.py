"""Command line for notekeeper."""

import argparse

from . import store


def build_parser():
    parser = argparse.ArgumentParser(prog="notekeeper", description="Keep short notes.")
    parser.add_argument("--store", help="the database file to use")
    sub = parser.add_subparsers(dest="command")
    add = sub.add_parser("add", help="add a note")
    add.add_argument("text", help="what the note says")
    add.add_argument("-t", "--tag", action="append", help="tag the note")
    listing = sub.add_parser("list", help="list the notes, newest first")
    listing.add_argument("--limit", type=int, default=20, help="show at most this many")
    sub.add_parser("search", help="find notes that contain a word")
    sub.add_parser("debug-dump", help=argparse.SUPPRESS)
    # sub.add_parser("legacy-import", help="import the old format")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    db = store.connect(args.store)
    return 0 if db else 1
