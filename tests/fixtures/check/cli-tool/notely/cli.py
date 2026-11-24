import argparse


def main():
    parser = argparse.ArgumentParser(prog="notely")
    parser.add_argument("text")
    parser.parse_args()
