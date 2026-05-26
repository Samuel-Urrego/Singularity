"""Shared fixtures for Singularity tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from singularity.types import ColumnInfo, Parameter, SPMetadata

# ---------------------------------------------------------------------------
# Mock pyodbc cursor fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_cursor() -> MagicMock:
    """Return a MagicMock that behaves like a pyodbc Cursor.

    The mock supports:
    - cursor.execute(sql, params) — no-op, returns self
    - cursor.fetchone() — returns None by default
    - cursor.fetchall() — returns [] by default

    Override by assigning to mock_cursor.fetchone.return_value
    or mock_cursor.fetchall.return_value in the test.
    """
    cursor = MagicMock()
    cursor.execute.return_value = cursor
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    return cursor


# ---------------------------------------------------------------------------
# Mock pyodbc connection fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_connection(mock_cursor: MagicMock) -> MagicMock:
    """Return a MagicMock that behaves like a pyodbc Connection.

    The connection provides cursor() which returns the existing mock_cursor.
    """
    connection = MagicMock()
    connection.cursor.return_value = mock_cursor
    return connection


# ---------------------------------------------------------------------------
# Sample SPMetadata fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_sp_metadata() -> SPMetadata:
    """Return SPMetadata for a typical 'usp_GetOrders' procedure."""
    return SPMetadata(
        name="usp_GetOrders",
        parameters=[
            Parameter(
                name="@OrderId",
                sql_type="INT",
                direction="IN",
                default=None,
                nullable=False,
            ),
            Parameter(
                name="@CustomerName",
                sql_type="NVARCHAR(100)",
                direction="IN",
                default=None,
                nullable=True,
            ),
        ],
        columns=[
            ColumnInfo(name="OrderId", sql_type="INT", nullable=False),
            ColumnInfo(name="CustomerName", sql_type="NVARCHAR(100)", nullable=True),
            ColumnInfo(name="OrderDate", sql_type="DATETIME", nullable=False),
            ColumnInfo(name="Total", sql_type="DECIMAL(18,2)", nullable=True),
        ],
    )


@pytest.fixture
def no_column_metadata() -> SPMetadata:
    """Return SPMetadata with no columns (action-only SP)."""
    return SPMetadata(
        name="usp_ExecuteOnly",
        parameters=[],
        columns=[],
    )


@pytest.fixture
def all_types_metadata() -> SPMetadata:
    """Return SPMetadata with one column per known SQL type."""
    return SPMetadata(
        name="usp_AllTypes",
        parameters=[],
        columns=[
            ColumnInfo(name="IntCol", sql_type="INT", nullable=True),
            ColumnInfo(name="BigIntCol", sql_type="BIGINT", nullable=True),
            ColumnInfo(name="SmallIntCol", sql_type="SMALLINT", nullable=True),
            ColumnInfo(name="TinyIntCol", sql_type="TINYINT", nullable=True),
            ColumnInfo(name="VarCharCol", sql_type="VARCHAR(50)", nullable=True),
            ColumnInfo(name="NVarCharCol", sql_type="NVARCHAR(100)", nullable=True),
            ColumnInfo(name="CharCol", sql_type="CHAR(10)", nullable=True),
            ColumnInfo(name="NCharCol", sql_type="NCHAR(10)", nullable=True),
            ColumnInfo(name="DateTimeCol", sql_type="DATETIME", nullable=True),
            ColumnInfo(name="DateCol", sql_type="DATE", nullable=True),
            ColumnInfo(name="BitCol", sql_type="BIT", nullable=True),
            ColumnInfo(name="DecimalCol", sql_type="DECIMAL(18,2)", nullable=True),
            ColumnInfo(name="FloatCol", sql_type="FLOAT", nullable=True),
            ColumnInfo(name="MoneyCol", sql_type="MONEY", nullable=True),
            ColumnInfo(name="GuidCol", sql_type="UNIQUEIDENTIFIER", nullable=True),
            ColumnInfo(name="UnknownCol", sql_type="HIERARCHYID", nullable=True),
        ],
    )


# ---------------------------------------------------------------------------
# Version string fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def modern_version_string() -> str:
    """SQL Server 2022 version string."""
    return (
        "Microsoft SQL Server 2022 (RTM-CU14) (KB1234567) - 16.0.4125.3 (X64)\n"
        "\tDec 12 2024 11:22:33\n"
        "\tCopyright (c) Microsoft Corporation\n"
        "\tStandard Edition (64-bit) on Windows Server 2022 Datacenter (X64)\n"
    )


@pytest.fixture
def legacy_version_string() -> str:
    """SQL Server 2012 version string."""
    return (
        "Microsoft SQL Server 2012 (SP4) (KB1234567) - 11.0.7507.2 (X64)\n"
        "\tMar  5 2024 10:30:00\n"
        "\tCopyright (c) Microsoft Corporation\n"
        "\tStandard Edition (64-bit) on Windows NT 6.3 <X64>\n"
    )


@pytest.fixture
def azure_version_string() -> str:
    """Azure SQL Database version string."""
    return (
        "Microsoft SQL Azure (RTM) - 12.0.2000.8\n"
        "\tFeb 20 2025 08:45:12\n"
        "\tCopyright (c) Microsoft Corporation\n"
    )


# ---------------------------------------------------------------------------
# Sample config TOML fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_toml_path(tmp_path):
    """Write a valid minimal config and return its path."""
    cfg = tmp_path / "valid_config.toml"
    cfg.write_text(
        "[connection]\n"
        'server = "localhost"\n'
        'database = "AdventureWorks"\n'
        'trusted_connection = true\n'
        "\n"
        "[sp_selection]\n"
        'procedures = ["usp_GetOrders", "usp_GetCustomers"]\n'
        "\n"
        "[output]\n"
        'directory = "models"\n'
        'mode = "source"\n'
        'naming_convention = "snake_case"\n'
        'file_naming = "{schema}_{sp_name}.py"\n'
    )
    return cfg
