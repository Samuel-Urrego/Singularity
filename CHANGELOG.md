# Changelog

All notable changes to Singularity will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-26

### Added

- SQL Server connection via pyodbc with automatic version detection (Modern, Legacy, Azure)
- Stored Procedure parameter introspection via `sys.parameters`
- First result set column metadata via `sp_describe_first_result_set`
- Pydantic v2 model generation in dynamic (`create_model()`) and source (`.py` file) modes
- Typer CLI with `singularity --config <toml>` command
- TOML configuration with Pydantic validation (connection, SP selection, output preferences)
- Field name sanitization with configurable naming conventions (snake_case, camelCase, PascalCase)
- File naming templates with `{schema}`, `{database}`, `{sp_name}` interpolation
- Strategy pattern for version-specific SQL Server introspection (Modern, Legacy, Azure)
- Legacy fallback using `sys.columns` + `sys.objects` join when `sp_describe_first_result_set` is unavailable
- 130 unit tests with 84% coverage
- UV package manager support
- Pre-commit hooks (ruff, mypy)
- GitHub Actions CI: test matrix (Windows + Linux, Python 3.10–3.13), lint, coverage
- PyPI trusted publishing via GitHub Actions
