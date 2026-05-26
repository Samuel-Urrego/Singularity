"""TOML configuration loading and Pydantic config models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator


class ConnectionConfig(BaseModel):
    """SQL Server connection settings."""

    server: str
    """Server hostname or IP address (required)."""

    database: str
    """Database name (required)."""

    driver: str = "ODBC Driver 18 for SQL Server"
    """ODBC driver name."""

    trusted_connection: bool = True
    """Use Windows Authentication when True."""

    username: str | None = None
    """SQL Server login username (used when trusted_connection is False)."""

    password: str | None = None
    """SQL Server login password (used when trusted_connection is False)."""

    def build_connection_string(self) -> str:
        """Build a pyodbc-compatible connection string from the config.

        Returns:
            A DRIVER=SERVER=DATABASE=... connection string.
        """
        parts = [
            f"DRIVER={{{self.driver}}}",
            f"SERVER={self.server}",
            f"DATABASE={self.database}",
        ]
        if self.trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            if self.username:
                parts.append(f"UID={self.username}")
            if self.password:
                parts.append(f"PWD={self.password}")
        return ";".join(parts)


class SpSelectionConfig(BaseModel):
    """Stored procedure selection criteria."""

    procedures: list[str] | None = None
    """Explicit list of stored procedure names to introspect."""

    pattern: str | None = None
    """Wildcard pattern (e.g. 'usp_%') to resolve against the database."""

    @field_validator("procedures", "pattern")
    @classmethod
    def _at_least_one(cls, v: list[str] | str | None) -> list[str] | str | None:
        return v


class OutputConfig(BaseModel):
    """Output preferences for generated models."""

    directory: str = "."
    """Output directory for generated files."""

    mode: Literal["dynamic", "source"] = "source"
    """Generation mode: 'dynamic' for runtime models, 'source' for .py files."""

    file_naming: str = "{sp_name}.py"
    """File naming template with {sp_name}, {schema}, {database} variables."""

    naming_convention: Literal["snake_case", "camelCase", "PascalCase"] = "snake_case"
    """Field naming convention for generated models."""

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        allowed = {"dynamic", "source"}
        if v not in allowed:
            raise ValueError(f"mode must be one of {allowed}, got '{v}'")
        return v

    @field_validator("naming_convention")
    @classmethod
    def _validate_convention(cls, v: str) -> str:
        allowed = {"snake_case", "camelCase", "PascalCase"}
        if v not in allowed:
            raise ValueError(
                f"naming_convention must be one of {allowed}, got '{v}'"
            )
        return v


class SingularityConfig(BaseModel):
    """Top-level configuration model."""

    connection: ConnectionConfig
    """SQL Server connection settings."""

    sp_selection: SpSelectionConfig
    """Stored procedure selection criteria."""

    output: OutputConfig = OutputConfig()
    """Output preferences (defaults apply if section omitted)."""


def load_config(path: str | Path) -> SingularityConfig:
    """Load and validate a TOML configuration file.

    Args:
        path: Path to the TOML config file.

    Returns:
        A validated SingularityConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        pydantic.ValidationError: If the config is invalid.
    """
    import tomli

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    data = tomli.loads(raw)

    return SingularityConfig(**data)
