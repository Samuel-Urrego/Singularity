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

    def _fetch_column_descriptions(
        self, sp_name: str, cursor: Any, columns: list[Any],
    ) -> dict[str, str]:
        """Query sys.extended_properties for column descriptions.

        Args:
            sp_name: The stored procedure name (schema-qualified if available).
            cursor: An active pyodbc Cursor.
            columns: List of ColumnInfo objects to look up descriptions for.

        Returns:
            A dict mapping column names to their descriptions.
        """
        if not columns:
            return {}

        descriptions: dict[str, str] = {}

        try:
            for col in columns:
                cursor.execute(
                    """
                    SELECT CAST(ep.value AS NVARCHAR(MAX))
                    FROM sys.extended_properties ep
                    WHERE ep.class = 1
                      AND ep.major_id = OBJECT_ID(?)
                      AND ep.minor_id = COLUMNPROPERTY(OBJECT_ID(?), ?, 'ColumnId')
                      AND ep.name = 'MS_Description'
                    """,
                    (sp_name, sp_name, col.name),
                )
                row = cursor.fetchone()
                if row and row[0] is not None:
                    descriptions[col.name] = str(row[0])
        except Exception:
            # Extended properties are optional — silently skip on failure
            pass

        return descriptions
