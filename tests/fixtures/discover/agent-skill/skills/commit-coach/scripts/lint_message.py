import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog="lint_message")
    parser.add_argument("--debug-dump", action="store_true")
    parser.add_argument("message")
    args = parser.parse_args()
    return 0 if len(args.message.splitlines()[0]) <= 72 else 1


if __name__ == "__main__":
    sys.exit(main())
