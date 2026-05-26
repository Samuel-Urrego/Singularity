"""Tests for the CLI generate command using Typer's CliRunner."""

import re

from typer.testing import CliRunner

from singularity.cli._app import app

runner = CliRunner()

# Rich output contains ANSI escape codes — strip them for assertions
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _clean(text: str) -> str:
    return _ANSI_RE.sub("", text)


class TestCliGenerate:
    """CLI generate command — integration tests at the Typer level."""

    def test_help_shows_generate(self) -> None:
        """--help output mentions the generate command or --config option."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        output = _clean(result.stdout).lower()
        assert "generate" in output or "--config" in output

    def test_missing_config_file(self) -> None:
        """Running with a non-existent config file shows an error."""
        result = runner.invoke(app, ["generate", "--config", "/nonexistent/path.toml"])
        assert result.exit_code in (1, 2)
        output = _clean(result.stdout + result.stderr).lower()
        assert "not found" in output or "error" in output or "exist" in output

    def test_generate_requires_config(self) -> None:
        """generate without --config shows error message."""
        result = runner.invoke(app, ["generate"])
        assert result.exit_code != 0
        output = _clean(result.stdout + result.stderr).lower()
        assert "error" in output or "option" in output or "missing" in output

    def test_generate_help(self) -> None:
        """generate --help shows option details."""
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--config" in _clean(result.stdout)

    def test_app_runs_successfully(self) -> None:
        """The CLI can be invoked at the top level."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_generate_with_empty_config_file(self, tmp_path) -> None:
        """An empty config file causes a validation error."""
        cfg = tmp_path / "empty.toml"
        cfg.write_text("")
        result = runner.invoke(app, ["generate", "--config", str(cfg)])
        assert result.exit_code in (1, 2)
        output = _clean(result.stdout + result.stderr).lower()
        assert "error" in output
