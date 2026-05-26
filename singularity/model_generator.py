"""Pydantic model generation from stored procedure metadata.

Provides a single generate_model() function with two output modes:
- "dynamic": returns a runtime BaseModel subclass via create_model()
- "source": returns a valid Python source code string
"""

from __future__ import annotations

import re
import warnings
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

from singularity.types import SPMetadata

# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------

TYPE_MAP: dict[str, type] = {
    # Integer types
    "INT": int,
    "BIGINT": int,
    "SMALLINT": int,
    "TINYINT": int,
    # String types
    "VARCHAR": str,
    "NVARCHAR": str,
    "CHAR": str,
    "NCHAR": str,
    # Date/time types
    "DATETIME": datetime,
    "DATETIME2": datetime,
    "DATE": datetime,
    "SMALLDATETIME": datetime,
    # Boolean
    "BIT": bool,
    # Float / decimal types
    "DECIMAL": float,
    "NUMERIC": float,
    "FLOAT": float,
    "REAL": float,
    "MONEY": float,
    "SMALLMONEY": float,
    # UUID / unique identifier
    "UNIQUEIDENTIFIER": str,
}

# Types whose Pydantic annotation differs from the Python type
PYDANTIC_TYPE_MAP: dict[type, type] = {
    datetime: datetime,
}

# ---------------------------------------------------------------------------
# Field name sanitization
# ---------------------------------------------------------------------------

_RESERVED_WORDS: set[str] = {
    "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from",
    "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
    "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "True", "False", "None",
}


def _to_snake_case(name: str) -> str:
    """Convert a name to snake_case."""
    # Insert underscore before uppercase letters preceded by a lowercase
    # letter or digit, then lowercase
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    # Also handle acronyms followed by uppercase (e.g. "XMLParser" → "xml_parser")
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    return s.lower()


def _to_camel_case(name: str) -> str:
    """Convert a name to camelCase (first letter lowercase)."""
    snake = _to_snake_case(name)
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _to_pascal_case(name: str) -> str:
    """Convert a name to PascalCase (first letter uppercase)."""
    snake = _to_snake_case(name)
    return "".join(p.capitalize() for p in snake.split("_"))


def sanitize_field_name(
    name: str,
    convention: Literal["snake_case", "camelCase", "PascalCase"] = "snake_case",
) -> str:
    """Convert a SQL identifier to a valid Python field name.

    Steps:
    1. Strip leading '@' characters (parameter prefix)
    2. Replace non-alphanumeric characters (except underscores) with '_'
    3. Collapse consecutive underscores
    4. Strip leading/trailing underscores
    5. Apply naming convention (snake_case / camelCase / PascalCase)
    6. Prefix with 'field_' if the result is a Python reserved word

    Args:
        name: The raw SQL identifier (e.g. '@OrderId', 'Customer Name').
        convention: The target naming convention.

    Returns:
        A valid Python identifier.
    """
    # Strip @ prefix (parameter marker)
    clean = name.lstrip("@")

    # Replace non-alphanumeric, non-underscore chars with underscores
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", clean)

    # Collapse multiple underscores
    clean = re.sub(r"_+", "_", clean)

    # Strip leading/trailing underscores
    clean = clean.strip("_")

    # If empty after sanitization, use a generic name
    if not clean:
        clean = "field"

    # Apply naming convention
    if convention == "camelCase":
        clean = _to_camel_case(clean)
    elif convention == "PascalCase":
        clean = _to_pascal_case(clean)
    else:
        # snake_case — ensure it's truly snake_case
        clean = _to_snake_case(clean)

    # Ensure it doesn't start with a digit
    if clean and clean[0].isdigit():
        clean = f"field_{clean}"

    # Avoid reserved words (case-insensitive check — after snake_case everything is lowercase)
    if clean.lower() in {w.lower() for w in _RESERVED_WORDS}:
        clean = f"field_{clean}"

    return clean


# ---------------------------------------------------------------------------
# Source code type name helpers
# ---------------------------------------------------------------------------

_SOURCE_TYPE_NAMES: dict[type, str] = {
    int: "int",
    str: "str",
    datetime: "datetime",
    bool: "bool",
    float: "float",
}


def _py_type_name(tp: type) -> str:
    """Return the Python source-level name for a type."""
    return _SOURCE_TYPE_NAMES.get(tp, "str")


# ---------------------------------------------------------------------------
# Model generation
# ---------------------------------------------------------------------------


def generate_model(
    meta: SPMetadata,
    mode: Literal["dynamic", "source"] = "source",
    naming_convention: Literal["snake_case", "camelCase", "PascalCase"] = "snake_case",
    result_set_index: int = 0,
) -> type[BaseModel] | str:
    """Generate a Pydantic v2 model from stored procedure metadata.

    Two output modes:
    - **dynamic**: Returns a BaseModel subclass (created via create_model()).
      The class can be used at runtime for type-safe data access.
    - **source**: Returns a valid Python source code string. The string
      contains proper imports, a class definition, typed fields, and a
      ``from_db()`` classmethod to execute the SP and return typed instances.

    Args:
        meta: SPMetadata describing the stored procedure's result set.
        mode: Output mode — "dynamic" or "source".
        naming_convention: Field naming convention:
            - "snake_case" (default): order_id, customer_name
            - "camelCase": orderId, customerName
            - "PascalCase": OrderId, CustomerName
        result_set_index: Which result set to generate a model for
            (0 = first). Ignored when ``mode="source"`` with multiple
            result sets — use ``generate_all_models()`` instead.

    Returns:
        A BaseModel subclass (dynamic mode) or a Python source string (source mode).

    Example:
        >>> meta = SPMetadata(name="usp_GetOrders", result_sets=[[
        ...     ColumnInfo(name="OrderId", sql_type="INT", nullable=False),
        ...     ColumnInfo(name="Total", sql_type="DECIMAL", nullable=True),
        ... ]])
        >>> model = generate_model(meta, mode="dynamic")
        >>> isinstance(model, type) and issubclass(model, BaseModel)
        True
    """
    if mode == "dynamic":
        return _generate_dynamic(meta, naming_convention)
    return _generate_source(meta, naming_convention)


def generate_all_models(
    meta: SPMetadata,
    mode: Literal["dynamic", "source"] = "source",
    naming_convention: Literal["snake_case", "camelCase", "PascalCase"] = "snake_case",
) -> type[BaseModel] | tuple[type[BaseModel], ...] | str | list[str]:
    """Generate models for ALL result sets of a stored procedure.

    For multi-result-set SPs, generates one model class per result set.
    For source mode, returns a list of source strings (one per class).
    For dynamic mode, returns a tuple of model classes.

    The last result set model includes ``from_db()`` which handles
    multiple result sets at execution time.
    """
    num_rs = len(meta.result_sets)

    if num_rs <= 1:
        # Single result set — delegate to generate_model
        result = generate_model(meta, mode=mode, naming_convention=naming_convention)
        if mode == "dynamic":
            return (result,)  # type: ignore[return-value]
        return [result]  # type: ignore[return-value]

    if mode == "dynamic":
        models: list[type[BaseModel]] = []
        for i, rs in enumerate(meta.result_sets):
            # Create a temporary meta with just this result set
            from singularity.types import ColumnInfo  # noqa: PLC0415 — local import for cycle safety

            temp_meta = meta.model_copy(update={"result_sets": [rs]})
            m = _generate_dynamic_single_rs(temp_meta, f"{meta.name}_Result{i + 1}", naming_convention)
            models.append(m)

        # Patch from_db on the LAST model to handle all RS
        _patch_from_db_multi(models, meta)

        return tuple(models)

    # Source mode — generate one class per result set
    sources: list[str] = []
    for i, rs in enumerate(meta.result_sets):
        from singularity.types import ColumnInfo  # noqa: PLC0415

        temp_meta = meta.model_copy(update={"result_sets": [rs]})
        suffix = f"Result{i + 1}" if i > 0 else ""
        src = _generate_source(temp_meta, naming_convention, class_suffix=suffix)
        sources.append(src)

    return sources


# ---------------------------------------------------------------------------
# Dynamic mode
# ---------------------------------------------------------------------------


def _resolve_py_type(sql_type: str) -> type:
    """Map a SQL Server type string to a Python type.

    Strips parenthesised qualifiers like (50), (18,2) before lookup.
    Falls back to ``str`` for unknown types.
    """
    base = sql_type.split("(")[0].strip().upper()
    py_type = TYPE_MAP.get(base)
    if py_type is None:
        warnings.warn(
            f"Unknown SQL Server type '{sql_type}' — falling back to str",
            stacklevel=2,
        )
        return str
    return py_type


def _generate_dynamic(
    meta: SPMetadata,
    naming_convention: str = "snake_case",
) -> type[BaseModel]:
    """Generate a runtime BaseModel subclass via create_model() for the first RS."""
    return _generate_dynamic_single_rs(meta, meta.name, naming_convention)


def _generate_dynamic_single_rs(
    meta: SPMetadata,
    class_name: str,
    naming_convention: str,
) -> type[BaseModel]:
    """Generate a dynamic model for a single result set."""
    fields: dict[str, Any] = {}

    for col in meta.columns:
        py_type = _resolve_py_type(col.sql_type)
        field_name = sanitize_field_name(col.name, naming_convention)  # type: ignore[arg-type]

        field_kwargs: dict[str, Any] = {}
        if col.description:
            field_kwargs["description"] = col.description

        if col.nullable:
            if field_kwargs:
                fields[field_name] = (type(None) | py_type, Field(default=None, **field_kwargs))
            else:
                fields[field_name] = (type(None) | py_type, None)
        else:
            if field_kwargs:
                fields[field_name] = (py_type, Field(..., **field_kwargs))
            else:
                fields[field_name] = (py_type, ...)

    # Add OUTPUT param fields (as Optional[T] = None)
    output_param_names: list[str] = []
    for p in meta.parameters:
        if p.direction in ("OUT", "INOUT"):
            py_type = _resolve_py_type(p.sql_type)
            field_name = sanitize_field_name(p.name, naming_convention)  # type: ignore[arg-type]
            output_param_names.append(p.name)
            fields[field_name] = (type(None) | py_type, None)

    model = create_model(class_name, **fields)
    model._output_param_names = output_param_names  # type: ignore[attr-defined]

    # Build param_order for executor
    all_param_names: list[str] = [p.name for p in meta.parameters]

    # Monkey-patch from_db() onto the dynamic model
    _patch_from_db(model, meta.name, output_param_names, all_param_names)

    return model


def _patch_from_db(
    model: type[BaseModel],
    sp_name: str,
    output_param_names: list[str] | None = None,
    all_param_names: list[str] | None = None,
) -> None:
    """Monkey-patch a ``from_db()`` classmethod onto a dynamic model.

    The patched method delegates to ``singularity.executor.execute_sp``,
    embedding the stored procedure name so callers only pass a connection
    string and parameter values.
    """
    from singularity.executor import execute_sp

    output_param_names = output_param_names or []
    all_param_names = all_param_names or []

    @classmethod  # type: ignore[misc]
    def from_db(cls: type[BaseModel], conn_str: str, **params: Any) -> list[BaseModel]:  # type: ignore[no-redef]
        return execute_sp(
            conn_str,
            sp_name,
            cls,
            input_params=params,
            output_param_names=output_param_names,
            param_order=all_param_names,
        )

    model.from_db = from_db  # type: ignore[attr-defined]


def _patch_from_db_multi(
    models: list[type[BaseModel]],
    meta: SPMetadata,
) -> None:
    """Monkey-patch a ``from_db()`` onto the last model for multi-RS SPs.

    The patched method returns ``list[tuple[Model1, Model2, ...]]``.
    """
    from singularity.executor import execute_sp_multi

    output_param_names = [p.name for p in meta.parameters if p.direction in ("OUT", "INOUT")]
    all_param_names = [p.name for p in meta.parameters]

    last_model = models[-1]

    @classmethod  # type: ignore[misc]
    def from_db(cls: type[BaseModel], conn_str: str, **params: Any) -> list[Any]:  # type: ignore[no-redef]
        return execute_sp_multi(
            conn_str,
            meta.name,
            models,
            input_params=params,
            output_param_names=output_param_names,
            param_order=all_param_names,
        )

    last_model.from_db = from_db  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Source mode
# ---------------------------------------------------------------------------


def _generate_source(
    meta: SPMetadata,
    naming_convention: str = "snake_case",
    class_suffix: str = "",
) -> str:
    """Generate a Python source code string for a Pydantic model."""
    class_name = sanitize_field_name(meta.name, "PascalCase") + class_suffix
    rs = meta.columns  # first result set via backward-compat property

    has_descriptions = any(col.description for col in rs)
    num_rs = len(meta.result_sets)
    is_single_rs = num_rs <= 1

    lines: list[str] = []
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from datetime import datetime")
    lines.append("from typing import Any, Optional")
    lines.append("from pydantic import BaseModel")
    if has_descriptions:
        lines.append("from pydantic import Field")
    if is_single_rs:
        lines.append("from singularity.executor import execute_sp")
    else:
        lines.append("from singularity.executor import execute_sp_multi")
    lines.append("")

    # Identify OUTPUT params
    output_params = [p for p in meta.parameters if p.direction in ("OUT", "INOUT")]
    output_param_names = [p.name for p in output_params]
    all_param_names = [p.name for p in meta.parameters]

    if not rs:
        lines.append(f"class {class_name}(BaseModel):")
        lines.append(f"    _sp_name = {repr(meta.name)}")
        lines.append(f"    _output_param_names = {repr(output_param_names)}")
        lines.append("")
        for p in output_params:
            field_name = sanitize_field_name(p.name, naming_convention)  # type: ignore[arg-type]
            lines.append(f"    {field_name}: Optional[Any] = None")
        if output_params:
            lines.append("")
        if is_single_rs:
            lines.append("    @classmethod")
            lines.append("    def from_db(cls, conn_str: str, **params: Any) -> list[BaseModel]:")
        else:
            lines.append("    @classmethod")
            lines.append(
                "    def from_db("
                "cls, conn_str: str, **params: Any"
                ") -> list[Any]:"
            )
        lines.append('        """Execute the stored procedure and return typed instances."""')
        if is_single_rs:
            lines.append("        return execute_sp(")
        else:
            lines.append("        return execute_sp_multi(")
        lines.append("            conn_str,")
        lines.append("            cls._sp_name,")
        if not is_single_rs:
            lines.append("            _MODELS,")
        lines.append("            cls,")
        lines.append("            input_params=params,")
        lines.append(f"            output_param_names={repr(output_param_names)},")
        lines.append(f"            param_order={repr(all_param_names)},")
        lines.append("        )")
        lines.append("")
        lines.append("    pass")
        lines.append("")
        return "\n".join(lines) + "\n"

    lines.append(f"class {class_name}(BaseModel):")
    lines.append(f'    """Model generated from stored procedure: {meta.name}.')
    lines.append("")
    lines.append('    Auto-generated by Singularity.')
    lines.append('    """')
    lines.append("")
    lines.append(f"    _sp_name = {repr(meta.name)}")
    lines.append("")

    for col in rs:
        py_type = _resolve_py_type(col.sql_type)
        field_name = sanitize_field_name(col.name, naming_convention)  # type: ignore[arg-type]
        type_name = _py_type_name(py_type)

        if col.description:
            if col.nullable:
                lines.append(
                    f"    {field_name}: Optional[{type_name}] = Field("
                    f"default=None, description={repr(col.description)})"
                )
            else:
                lines.append(
                    f"    {field_name}: {type_name} = Field("
                    f"description={repr(col.description)})"
                )
        else:
            if col.nullable:
                lines.append(f"    {field_name}: Optional[{type_name}] = None")
            else:
                lines.append(f"    {field_name}: {type_name}")

    # Add OUTPUT param fields (Optional[T] = None)
    for p in output_params:
        py_type = _resolve_py_type(p.sql_type)
        field_name = sanitize_field_name(p.name, naming_convention)  # type: ignore[arg-type]
        type_name = _py_type_name(py_type)
        lines.append(f"    {field_name}: Optional[{type_name}] = None")

    # Store output param names for executor
    if output_param_names:
        lines.append(f"    _output_param_names = {repr(output_param_names)}")
    else:
        lines.append("    _output_param_names: list[str] = []")

    lines.append("")
    if is_single_rs:
        lines.append("    @classmethod")
        lines.append("    def from_db(cls, conn_str: str, **params: Any) -> list[BaseModel]:")
    else:
        lines.append("    @classmethod")
        lines.append(
            "    def from_db("
            "cls, conn_str: str, **params: Any"
            ") -> list[Any]:"
        )
    lines.append('        """Execute the stored procedure and return typed instances."""')
    if is_single_rs:
        lines.append("        return execute_sp(")
    else:
        lines.append("        return execute_sp_multi(")
    lines.append("            conn_str,")
    lines.append("            cls._sp_name,")
    if not is_single_rs:
        lines.append("            _MODELS,")
    lines.append("            cls,")
    lines.append("            input_params=params,")
    lines.append(f"            output_param_names={repr(output_param_names)},")
    lines.append(f"            param_order={repr(all_param_names)},")
    lines.append("        )")
    lines.append("")
    return "\n".join(lines) + "\n"
