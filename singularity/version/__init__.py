"""Server version detection and strategy factory.

Parses SQL Server @@VERSION output and selects the appropriate
introspection strategy.
"""

from __future__ import annotations

from enum import Enum

from singularity.version._azure import AzureIntrospector
from singularity.version._base import VersionIntrospector
from singularity.version._legacy import LegacyIntrospector
from singularity.version._modern import ModernIntrospector


class ServerVersion(Enum):
    """Supported SQL Server version targets."""

    MODERN = "modern"
    """SQL Server 2016 and later."""

    LEGACY = "legacy"
    """SQL Server 2008–2014."""

    AZURE = "azure"
    """Azure SQL Database."""


def _select_strategy(version: ServerVersion) -> VersionIntrospector:
    """Return the introspection strategy for the given server version.

    Args:
        version: A ServerVersion enum value.

    Returns:
        A concrete VersionIntrospector instance.
    """
    mapping: dict[ServerVersion, type[VersionIntrospector]] = {
        ServerVersion.MODERN: ModernIntrospector,
        ServerVersion.LEGACY: LegacyIntrospector,
        ServerVersion.AZURE: AzureIntrospector,
    }
    cls = mapping[version]
    return cls()


def parse_version_string(version_output: str) -> ServerVersion:
    """Parse a @@VERSION string and return the matching ServerVersion.

    Detection logic:
    - Contains 'Azure SQL' → AZURE
    - Contains '2016' or higher year → MODERN
    - Otherwise → LEGACY

    Args:
        version_output: The raw output from SELECT @@VERSION.

    Returns:
        The detected ServerVersion.
    """
    upper = version_output.upper()

    if "AZURE" in upper or "SQL AZURE" in upper:
        return ServerVersion.AZURE

    # Check for SQL Server 2016 or later by looking for the year
    for year in ("2016", "2017", "2019", "2022"):
        if year in upper:
            return ServerVersion.MODERN

    return ServerVersion.LEGACY


__all__ = [
    "ServerVersion",
    "VersionIntrospector",
    "_select_strategy",
    "parse_version_string",
]
