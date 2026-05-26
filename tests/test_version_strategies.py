"""Tests for version-specific introspection strategies with mock cursors."""

from unittest.mock import MagicMock

import pytest

from singularity.exceptions import SpNotFoundError
from singularity.types import SPMetadata
from singularity.version._azure import AzureIntrospector
from singularity.version._legacy import LegacyIntrospector
from singularity.version._modern import ModernIntrospector


def _make_cursor(
    exists: bool = True,
    param_rows: list | None = None,
    column_rows: list | None = None,
    column_side_effect: type[Exception] | None = None,
) -> MagicMock:
    """Build a mock cursor with configurable fetch results.

    The cursor supports:
    - ``execute(sql, params)`` → returns self
    - ``fetchone()`` → ``[1]`` if *exists* else ``[0]``
    - ``fetchall()`` → returns the configured rows

    You can also pass *column_side_effect* to make the column query raise
    (e.g. ``Exception`` to test the fallback path in LegacyIntrospector).
    """
    cursor = MagicMock()
    cursor.execute.return_value = cursor
    cursor.fetchone.return_value = [1] if exists else [0]

    if column_side_effect is not None:
        call_count: int = 0

        def _fetchall_side_effect() -> list:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return param_rows or []
            raise column_side_effect("Column query failed")

        cursor.fetchall.side_effect = _fetchall_side_effect
    else:
        cursor.fetchall.side_effect = [param_rows or [], column_rows or []]

    return cursor


# ---------------------------------------------------------------------------
# Parameter data (shared across strategies)
# ---------------------------------------------------------------------------


PARAM_ROWS = [
    ("@OrderId", "int", "IN", 0, 0),
    ("@CustomerName", "nvarchar", "IN", 0, 1),
    ("@Total", "decimal", "IN", 0, 1),
]


class TestModernIntrospector:
    """ModernIntrospector (SQL Server 2016+)."""

    def test_returns_sp_metadata(self) -> None:
        """introspect() returns SPMetadata with parameters and columns."""
        cursor = _make_cursor(exists=True, param_rows=PARAM_ROWS, column_rows=[])
        result = ModernIntrospector().introspect("usp_Test", cursor)
        assert isinstance(result, SPMetadata)
        assert result.name == "usp_Test"
        assert len(result.parameters) == 3

    def test_parameter_fields(self) -> None:
        """Parameter fields are populated correctly."""
        cursor = _make_cursor(exists=True, param_rows=PARAM_ROWS, column_rows=[])
        result = ModernIntrospector().introspect("usp_Test", cursor)
        param = result.parameters[0]
        assert param.name == "@OrderId"
        assert param.sql_type == "INT"
        assert param.direction == "IN"
        assert param.default is None
        assert param.nullable is False

    def test_nullable_parameter(self) -> None:
        """A nullable parameter is reflected."""
        cursor = _make_cursor(exists=True, param_rows=PARAM_ROWS, column_rows=[])
        result = ModernIntrospector().introspect("usp_Test", cursor)
        param = result.parameters[1]
        assert param.name == "@CustomerName"
        assert param.nullable is True

    def test_inout_direction_normalised(self) -> None:
        """Direction is preserved as-is from the SQL CASE expression."""
        rows = [("@Id", "int", "INOUT", 0, 0)]
        cursor = _make_cursor(exists=True, param_rows=rows, column_rows=[])
        result = ModernIntrospector().introspect("usp_Test", cursor)
        assert result.parameters[0].direction == "INOUT"

    def test_sp_not_found(self) -> None:
        """Non-existent SP raises SpNotFoundError."""
        cursor = _make_cursor(exists=False)
        with pytest.raises(SpNotFoundError, match="usp_Missing"):
            ModernIntrospector().introspect("usp_Missing", cursor)

    def test_no_parameters(self) -> None:
        """SP with no parameters returns empty list."""
        cursor = _make_cursor(exists=True, param_rows=[], column_rows=[])
        result = ModernIntrospector().introspect("usp_NoParams", cursor)
        assert result.parameters == []

    def test_result_set_columns(self) -> None:
        """Result set columns are parsed correctly.

        sp_describe_first_result_set columns (6+):
        row[0]=is_hidden, row[1]=column_ordinal, row[2]=name,
        row[3]=is_nullable, row[4]=system_type_id, row[5]=system_type_name
        """
        # row[2]=name, row[3]=0 (not nullable), row[5]=system_type_name
        col_rows = [("hidden", 1, "OrderId", 0, 56, "int")]
        cursor = _make_cursor(exists=True, param_rows=[], column_rows=col_rows)
        result = ModernIntrospector().introspect("usp_Test", cursor)
        assert len(result.columns) == 1
        assert result.columns[0].name == "OrderId"
        assert result.columns[0].sql_type == "INT"
        assert result.columns[0].nullable is False

    def test_nullable_column(self) -> None:
        """A nullable column is reflected (row[3]=1)."""
        col_rows = [("hidden", 1, "Total", 1, 106, "decimal")]
        cursor = _make_cursor(exists=True, param_rows=[], column_rows=col_rows)
        result = ModernIntrospector().introspect("usp_Test", cursor)
        assert result.columns[0].nullable is True

    def test_column_query_failure_returns_empty(self) -> None:
        """When sp_describe_first_result_set fails, columns are empty."""
        cursor = _make_cursor(
            exists=True, param_rows=[], column_side_effect=Exception
        )
        result = ModernIntrospector().introspect("usp_Test", cursor)
        assert result.columns == []

    def test_schema_qualified_sp_name(self) -> None:
        """Schema-prefixed SP name is handled (strips prefix for lookup)."""
        cursor = _make_cursor(exists=True, param_rows=[], column_rows=[])
        result = ModernIntrospector().introspect("dbo.usp_Test", cursor)
        assert result.name == "dbo.usp_Test"


class TestLegacyIntrospector:
    """LegacyIntrospector (SQL Server 2008–2014)."""

    def test_returns_sp_metadata(self) -> None:
        """introspect() returns SPMetadata with parameters and columns."""
        cursor = _make_cursor(exists=True, param_rows=PARAM_ROWS, column_rows=[])
        result = LegacyIntrospector().introspect("usp_Test", cursor)
        assert isinstance(result, SPMetadata)

    def test_legacy_parameter_defaults(self) -> None:
        """Legacy uses has_default_value for default handling."""
        rows = [("@Id", "int", "IN", 0, 0), ("@Name", "nvarchar", "IN", 1, 1)]
        cursor = _make_cursor(exists=True, param_rows=rows, column_rows=[])
        result = LegacyIntrospector().introspect("usp_Test", cursor)
        assert result.parameters[0].default is None  # has_default = 0
        assert result.parameters[1].default == "(default)"  # has_default = 1

    def test_sp_not_found(self) -> None:
        """Non-existent SP raises SpNotFoundError."""
        cursor = _make_cursor(exists=False)
        with pytest.raises(SpNotFoundError):
            LegacyIntrospector().introspect("usp_Missing", cursor)

    def test_column_fallback_on_failure(self) -> None:
        """Legacy falls back to sys.objects+sys.columns when sp_describe fails."""
        cursor = _make_cursor(
            exists=True, param_rows=[], column_side_effect=Exception
        )
        result = LegacyIntrospector().introspect("usp_Test", cursor)
        # Fallback also fails (same mock), so columns stay empty
        assert result.columns == []

    def test_no_result_set(self) -> None:
        """SP with no result set returns empty columns."""
        cursor = _make_cursor(exists=True, param_rows=[], column_rows=[])
        result = LegacyIntrospector().introspect("usp_NoResult", cursor)
        assert result.columns == []

    def test_legacy_column_rows(self) -> None:
        """Legacy column rows from sys.columns have 3 fields: name, data_type, is_nullable."""
        # Force sp_describe to fail so fallback to sys.objects+sys.columns runs.
        # Then the fallback's fetchall gets the column rows.
        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchone.return_value = [1]  # SP exists
        col_rows = [("Id", "int", 0)]
        # call 1: param fetchall → []
        # call 2: sp_describe fetchall → raises Exception → caught, triggers fallback
        # call 3: fallback fetchall → col_rows
        cursor.fetchall.side_effect = [[], Exception("sp_describe fails"), col_rows]
        result = LegacyIntrospector().introspect("usp_Test", cursor)
        assert result.columns[0].name == "Id"
        assert result.columns[0].sql_type == "INT"
        assert result.columns[0].nullable is False


class TestAzureIntrospector:
    """AzureIntrospector (Azure SQL Database)."""

    def test_returns_sp_metadata(self) -> None:
        """introspect() returns SPMetadata with parameters and columns."""
        cursor = _make_cursor(exists=True, param_rows=PARAM_ROWS, column_rows=[])
        result = AzureIntrospector().introspect("usp_Test", cursor)
        assert isinstance(result, SPMetadata)

    def test_parameter_fields(self) -> None:
        """Parameter fields are populated correctly (Azure)."""
        cursor = _make_cursor(exists=True, param_rows=PARAM_ROWS, column_rows=[])
        result = AzureIntrospector().introspect("usp_Test", cursor)
        assert result.parameters[0].name == "@OrderId"
        assert result.parameters[0].sql_type == "INT"

    def test_sp_not_found(self) -> None:
        """Non-existent SP raises SpNotFoundError."""
        cursor = _make_cursor(exists=False)
        with pytest.raises(SpNotFoundError):
            AzureIntrospector().introspect("usp_Missing", cursor)

    def test_azure_column_metadata(self) -> None:
        """Azure columns from sys.dm_exec_describe_first_result_set (3 fields)."""
        col_rows = [("OrderId", "int", 0)]
        cursor = _make_cursor(exists=True, param_rows=[], column_rows=col_rows)
        result = AzureIntrospector().introspect("usp_Test", cursor)
        assert len(result.columns) == 1
        assert result.columns[0].name == "OrderId"
        assert result.columns[0].sql_type == "INT"

    def test_nullable_column_azure(self) -> None:
        """Azure column nullable is read from row[2]."""
        col_rows = [("Total", "decimal", 1)]  # row[2]=1 → nullable
        cursor = _make_cursor(exists=True, param_rows=[], column_rows=col_rows)
        result = AzureIntrospector().introspect("usp_Test", cursor)
        assert result.columns[0].nullable is True

    def test_column_failure_returns_empty(self) -> None:
        """When Azure DMV fails, columns are empty."""
        cursor = _make_cursor(
            exists=True, param_rows=[], column_side_effect=Exception
        )
        result = AzureIntrospector().introspect("usp_Test", cursor)
        assert result.columns == []

    def test_schema_qualified_name(self) -> None:
        """Schema-prefixed SP name (e.g. 'dbo.usp_Test') is handled."""
        cursor = _make_cursor(exists=True, param_rows=[], column_rows=[])
        result = AzureIntrospector().introspect("dbo.usp_Test", cursor)
        assert result.name == "dbo.usp_Test"
