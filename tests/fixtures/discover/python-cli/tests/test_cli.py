import argparse
import unittest


class CliTest(unittest.TestCase):
    def test_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--debug-trace", action="store_true")
        sub = parser.add_subparsers()
        sub.add_parser("selftest")
