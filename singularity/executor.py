"""Execute stored procedures and map results to Pydantic models.

Provides the runtime machinery for the ``from_db()`` classmethod
generated on Pydantic models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def execute_sp(
    conn_str: str,
    sp_name: str,
    model: type[BaseModel],
    params: dict[str, Any] | None = None,
) -> list[BaseModel]:
    """Execute a stored procedure and map result rows to model instances.

    Args:
        conn_str: A pyodbc-compatible connection string.
        sp_name: The stored procedure name (schema-qualified if applicable).
        model: The Pydantic model class to map each result row to.
        params: Input parameter values keyed by parameter name
            (with or without ``@`` prefix).

    Returns:
        A list of model instances, one per result row.
        Returns an empty list if the procedure produces no result rows.
    """
    import pyodbc

    conn = pyodbc.connect(conn_str)
    try:
        cursor = conn.cursor()

        # Build a parameterised EXEC call
        param_parts: list[str] = []
        param_values: list[Any] = []
        if params:
            for name, value in params.items():
                clean_name = name.lstrip("@")
                param_parts.append(f"@{clean_name}=?")
                param_values.append(value)

        sql = f"EXEC {sp_name}"
        if param_parts:
            sql += " " + ", ".join(param_parts)

        cursor.execute(sql, param_values)

        columns = [col[0] for col in cursor.description] if cursor.description else []

        result: list[BaseModel] = []
        for row in cursor.fetchall():
            row_data: dict[str, Any] = {}
            for i, col_name in enumerate(columns):
                row_data[col_name] = row[i]  # None stays None
            result.append(model(**row_data))

        return result
    finally:
        conn.close()
