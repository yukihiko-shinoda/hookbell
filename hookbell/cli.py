# Copyright (c) 2026 Yukihiko Shinoda
"""Console script for hookbell."""

import sys

import click


@click.command()
def main() -> int:
    """Console script for hookbell."""
    click.echo(
        "Replace this message by putting your code into hookbell.cli.main",
    )
    click.echo("See click documentation at https://click.palletsprojects.com/")
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
