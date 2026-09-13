"""Command-line entry point for `fw`."""

import argparse
from importlib.metadata import version


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="fw", description="Attention firewall.")
    parser.add_argument("--version", action="version", version=version("attention-firewall"))
    parser.parse_args(argv)


if __name__ == "__main__":
    main()
