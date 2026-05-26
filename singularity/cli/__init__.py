"""Singularity CLI — Typer app and commands."""

from singularity.cli._app import _main, app

__all__ = ["app", "main"]

# main is an alias for _main for entry point consistency
main = _main
