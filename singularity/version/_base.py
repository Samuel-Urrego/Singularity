"""Abstract base class for version-specific introspection strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from singularity.types import SPMetadata


class VersionIntrospector(ABC):
    """Strategy for introspecting stored procedure metadata for a specific
    SQL Server version or platform.

    Each concrete implementation knows the correct system views, functions,
    and DMVs to query for parameter and result set metadata.
    """

    @abstractmethod
    def introspect(self, sp_name: str, cursor: Any) -> SPMetadata:
        """Introspect a stored procedure and return its metadata.

        Args:
            sp_name: The stored procedure name (with or without schema).
            cursor: An active pyodbc Cursor connected to the database.

        Returns:
            SPMetadata containing parameters and result set column info.

        Raises:
            SpNotFoundError: If the stored procedure does not exist.
        """
        ...
