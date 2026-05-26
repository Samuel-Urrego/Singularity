"""Singularity Typer app instance — isolated to avoid circular imports."""

import sys

import typer


def _main() -> None:
    """Entry point with UTF-8 encoding support for Windows consoles."""
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    app()


app = typer.Typer(
    name="singularity",
    help="SQL Server stored procedure introspection and Pydantic model generator.",
    no_args_is_help=True,
    invoke_without_command=True,
)

# Register commands — import triggers @app.command() decorators
import singularity.cli.generate  # noqa: E402, F401 — registers generate command
