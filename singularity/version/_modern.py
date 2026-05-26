"""Introspection strategy for SQL Server 2016 and later.

Uses INFORMATION_SCHEMA.PARAMETERS for parameter metadata and
sp_describe_first_result_set for result set column metadata.
"""

from __future__ import annotations

from typing import Any

from singularity.exceptions import SpNotFoundError
from singularity.types import ColumnInfo, Parameter, SPMetadata
from singularity.version._base import VersionIntrospector


class ModernIntrospector(VersionIntrospector):
    """Strategy for SQL Server 2016+ using INFORMATION_SCHEMA + sp_describe_first_result_set."""

    def introspect(self, sp_name: str, cursor: Any) -> SPMetadata:
        """Introspect a stored procedure using modern SQL Server system views.

        Args:
            sp_name: The stored procedure name.
            cursor: An active pyodbc Cursor.

        Returns:
            SPMetadata with parameters and result set columns.

        Raises:
            SpNotFoundError: If the procedure does not exist.
        """
        # Strip schema prefix for lookup if present
        simple_name = sp_name.split(".")[-1] if "." in sp_name else sp_name

        # Verify the procedure exists
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.ROUTINES
            WHERE ROUTINE_TYPE = 'PROCEDURE'
              AND ROUTINE_NAME = ?
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
                    WHEN p.is_output = 0 AND p.is_readonly = 0 THEN 'IN'
                    ELSE 'INOUT'
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
            raw_name: str = row[0]  # e.g. "@OrderId"
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

        # Fetch all result sets via sp_describe_first_result_set
        result_sets: list[list[ColumnInfo]] = []
        try:
            tsql = f"EXEC {sp_name}"
            for idx in range(10):
                cursor.execute(
                    "{CALL sp_describe_first_result_set(?, NULL, ?)}",
                    (tsql, idx),
                )
                rows = cursor.fetchall()
                columns = [
                    ColumnInfo(
                        name=row[2],  # name (index 2)
                        sql_type=(row[5] or "UNKNOWN").upper(),  # system_type_name (index 5)
                        nullable=bool(row[3]),  # is_nullable (index 3)
                    )
                    for row in rows
                    if row[2] is not None  # skip unnamed columns
                ]
                if not columns:
                    break
                result_sets.append(columns)
        except Exception:
            # If sp_describe_first_result_set fails (e.g. dynamic SQL),
            # return empty result sets rather than crashing.
            pass

        # Enrich with column descriptions from extended properties
        for rs in result_sets:
            descriptions = self._fetch_column_descriptions(sp_name, cursor, rs)
            for col in rs:
                col.description = descriptions.get(col.name)

        return SPMetadata(name=sp_name, parameters=parameters, result_sets=result_sets)
