"""Introspection strategy for Azure SQL Database.

Uses sys.parameters for parameter metadata and
sys.dm_exec_describe_first_result_set for result set column metadata.
"""

from __future__ import annotations

from typing import Any

from singularity.exceptions import SpNotFoundError
from singularity.types import ColumnInfo, Parameter, SPMetadata
from singularity.version._base import VersionIntrospector


class AzureIntrospector(VersionIntrospector):
    """Strategy for Azure SQL Database: sys.parameters + sys.dm_exec_describe_first_result_set."""

    def introspect(self, sp_name: str, cursor: Any) -> SPMetadata:
        """Introspect a stored procedure on Azure SQL Database.

        Args:
            sp_name: The stored procedure name.
            cursor: An active pyodbc Cursor.

        Returns:
            SPMetadata with parameters and result set columns.

        Raises:
            SpNotFoundError: If the procedure does not exist.
        """
        simple_name = sp_name.split(".")[-1] if "." in sp_name else sp_name

        # Verify the procedure exists
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM sys.objects
            WHERE type = 'P'
              AND name = ?
            """,
            (simple_name,),
        )
        if cursor.fetchone()[0] == 0:
            raise SpNotFoundError(sp_name)

        # Fetch parameter metadata from sys.parameters
        cursor.execute(
            """
            SELECT
                p.name,
                tp.name AS data_type,
                CASE
                    WHEN p.is_output = 1 THEN 'OUT'
                    ELSE 'IN'
                END AS param_mode,
                p.has_default_value,
                p.is_nullable
            FROM sys.parameters p
            JOIN sys.types tp ON p.user_type_id = tp.user_type_id
            JOIN sys.objects o ON p.object_id = o.object_id
            WHERE o.type = 'P'
              AND o.name = ?
            ORDER BY p.parameter_id
            """,
            (simple_name,),
        )

        parameters: list[Parameter] = []
        for row in cursor.fetchall():
            raw_name: str = row[0]
            sql_type: str = row[1]
            direction: str = row[2]
            has_default: bool = row[3] or False
            nullable: bool = row[4] or False

            parameters.append(
                Parameter(
                    name=raw_name,
                    sql_type=sql_type.upper(),
                    direction=direction,  # type: ignore[arg-type]
                    default=None if not has_default else "(default)",
                    nullable=nullable,
                )
            )

        # Fetch result sets using Azure's DMV (first result set only)
        result_sets: list[list[ColumnInfo]] = []
        try:
            cursor.execute(
                """
                SELECT
                    name,
                    system_type_name,
                    is_nullable
                FROM sys.dm_exec_describe_first_result_set(
                    N'EXEC ' + QUOTENAME(?), NULL, 0
                )
                """,
                (simple_name,),
            )
            columns = [
                ColumnInfo(
                    name=row[0],  # name
                    sql_type=(row[1] or "UNKNOWN").upper(),  # system_type_name
                    nullable=bool(row[2]),  # is_nullable
                )
                for row in cursor.fetchall()
                if row[0] is not None
            ]
            if columns:
                result_sets.append(columns)
        except Exception:
            pass

        # Enrich with column descriptions from extended properties
        for rs in result_sets:
            descriptions = self._fetch_column_descriptions(sp_name, cursor, rs)
            for col in rs:
                col.description = descriptions.get(col.name)

        return SPMetadata(name=sp_name, parameters=parameters, result_sets=result_sets)
