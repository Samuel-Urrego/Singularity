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
    input_params: dict[str, Any] | None = None,
    output_param_names: list[str] | None = None,
    param_order: list[str] | None = None,
) -> list[BaseModel]:
    """Execute a stored procedure and map result rows to model instances.

    Handles both result sets and OUTPUT parameters.

    Args:
        conn_str: A pyodbc-compatible connection string.
        sp_name: The stored procedure name (schema-qualified if applicable).
        model: The Pydantic model class to map each result row to.
        input_params: Input parameter values keyed by parameter name
            (with or without ``@`` prefix).
        output_param_names: List of OUTPUT parameter names (with ``@`` prefix).
        param_order: Ordered list of ALL parameter names (input + output)
            as defined by the SP. This ensures correct positional binding.

    Returns:
        A list of model instances, one per result row.
        When the SP has OUTPUT params and no result rows, returns a single
        model instance with output values populated.
    """
    import pyodbc

    input_params = input_params or {}
    output_param_names = output_param_names or []
    param_order = param_order or list(input_params.keys())

    conn = pyodbc.connect(conn_str)
    try:
        cursor = conn.cursor()

        # Build the ordered call_params list
        call_params: list[Any] = []
        for name in param_order:
            if name in output_param_names:
                call_params.append(pyodbc.Output(str))
            else:
                lookup = name.lstrip("@")
                call_params.append(input_params.get(name) or input_params.get(lookup))

        # Build EXEC with named parameters
        named_parts: list[str] = []
        for i, name in enumerate(param_order):
            if name in output_param_names:
                named_parts.append(f"{name}=? OUTPUT")
            else:
                named_parts.append(f"{name}=?")

        tsql = f"EXEC {sp_name} {', '.join(named_parts)}"
        cursor.execute(tsql, call_params)

        # Read result rows
        columns = [col[0] for col in cursor.description] if cursor.description else []

        result: list[BaseModel] = []
        for row in cursor.fetchall():
            row_data: dict[str, Any] = {}
            for i, col_name in enumerate(columns):
                row_data[col_name] = row[i]  # None stays None
            result.append(model(**row_data))

        # If no result rows but there are output params, create a single instance
        if not result and output_param_names:
            result.append(model())

        # Populate output param values on each result instance (or the single one)
        if output_param_names:
            for inst in result:
                for name in output_param_names:
                    clean = name.lstrip("@")
                    idx = param_order.index(name)
                    val = call_params[idx].getvalue()
                    setattr(inst, clean, val)

        return result
    finally:
        conn.close()


def execute_sp_multi(
    conn_str: str,
    sp_name: str,
    models: list[type[BaseModel]],
    input_params: dict[str, Any] | None = None,
    output_param_names: list[str] | None = None,
    param_order: list[str] | None = None,
) -> list[tuple[BaseModel, ...]]:
    """Execute a stored procedure with multiple result sets.

    Executes the SP, iterates through all result sets using
    ``cursor.nextset()``, and maps each result set to its corresponding
    model class. Returns a list of tuples — one tuple per row cycle
    across result sets.

    Args:
        conn_str: A pyodbc-compatible connection string.
        sp_name: The stored procedure name.
        models: List of model classes, one per expected result set.
        input_params: Input parameter values.
        output_param_names: List of OUTPUT parameter names.
        param_order: Ordered list of ALL parameter names.

    Returns:
        A list of tuples. Each tuple contains one instance per model,
        in the same order as ``models``. Stops at the shortest result
        set if they differ in length.
    """
    import pyodbc

    input_params = input_params or {}
    output_param_names = output_param_names or []
    param_order = param_order or list(input_params.keys())

    conn = pyodbc.connect(conn_str)
    try:
        cursor = conn.cursor()

        # Build the ordered call_params list
        call_params: list[Any] = []
        for name in param_order:
            if name in output_param_names:
                call_params.append(pyodbc.Output(str))
            else:
                lookup = name.lstrip("@")
                call_params.append(input_params.get(name) or input_params.get(lookup))

        # Build EXEC with named parameters
        named_parts: list[str] = []
        for name in param_order:
            if name in output_param_names:
                named_parts.append(f"{name}=? OUTPUT")
            else:
                named_parts.append(f"{name}=?")

        tsql = f"EXEC {sp_name} {', '.join(named_parts)}"
        cursor.execute(tsql, call_params)

        # Collect all result sets with column names
        all_rs_columns: list[list[str]] = []
        all_rs_rows: list[list[list[Any]]] = []

        while True:
            columns = [col[0] for col in cursor.description] if cursor.description else []
            if not columns:
                if not cursor.nextset():
                    break
                continue
            all_rs_columns.append(columns)
            rows_data: list[list[Any]] = [list(row) for row in cursor.fetchall()]
            all_rs_rows.append(rows_data)
            if not cursor.nextset():
                break

        # Build tuples — one per row cycle across result sets
        result: list[tuple[BaseModel, ...]] = []
        if all_rs_rows:
            min_len = min(len(rs) for rs in all_rs_rows)
            for row_idx in range(min_len):
                instances: list[BaseModel] = []
                for rs_idx, rs_rows in enumerate(all_rs_rows):
                    model_cls = models[rs_idx] if rs_idx < len(models) else models[-1]
                    row_data = dict(zip(all_rs_columns[rs_idx], rs_rows[row_idx]))
                    instances.append(model_cls(**row_data))
                result.append(tuple(instances))

        # Populate output param values
        if output_param_names:
            for inst_tuple in result:
                for name in output_param_names:
                    clean = name.lstrip("@")
                    idx = param_order.index(name)
                    val = call_params[idx].getvalue()
                    for inst in inst_tuple:
                        if clean in inst.model_fields:
                            setattr(inst, clean, val)

        # If no result rows but there are output params
        if not result and output_param_names:
            inst = models[0]()
            for name in output_param_names:
                clean = name.lstrip("@")
                idx = param_order.index(name)
                val = call_params[idx].getvalue()
                if clean in inst.model_fields:
                    setattr(inst, clean, val)
            result.append((inst,))

        return result
    finally:
        conn.close()
