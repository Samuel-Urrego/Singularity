"""Tests for SQL Server → Python type mapping."""

from datetime import datetime

from singularity.model_generator import _resolve_py_type


class TestResolvePyType:
    """_resolve_py_type() maps SQL type strings to Python types."""

    def test_int(self) -> None:
        assert _resolve_py_type("INT") is int

    def test_bigint(self) -> None:
        assert _resolve_py_type("BIGINT") is int

    def test_smallint(self) -> None:
        assert _resolve_py_type("SMALLINT") is int

    def test_tinyint(self) -> None:
        assert _resolve_py_type("TINYINT") is int

    def test_varchar(self) -> None:
        assert _resolve_py_type("VARCHAR(50)") is str

    def test_nvarchar(self) -> None:
        assert _resolve_py_type("NVARCHAR(100)") is str

    def test_char(self) -> None:
        assert _resolve_py_type("CHAR(10)") is str

    def test_nchar(self) -> None:
        assert _resolve_py_type("NCHAR(10)") is str

    def test_datetime(self) -> None:
        assert _resolve_py_type("DATETIME") is datetime

    def test_datetime2(self) -> None:
        assert _resolve_py_type("DATETIME2") is datetime

    def test_date(self) -> None:
        assert _resolve_py_type("DATE") is datetime

    def test_smalldatetime(self) -> None:
        assert _resolve_py_type("SMALLDATETIME") is datetime

    def test_bit(self) -> None:
        assert _resolve_py_type("BIT") is bool

    def test_decimal(self) -> None:
        assert _resolve_py_type("DECIMAL(18,2)") is float

    def test_numeric(self) -> None:
        assert _resolve_py_type("NUMERIC(10,2)") is float

    def test_float(self) -> None:
        assert _resolve_py_type("FLOAT") is float

    def test_real(self) -> None:
        assert _resolve_py_type("REAL") is float

    def test_money(self) -> None:
        assert _resolve_py_type("MONEY") is float

    def test_smallmoney(self) -> None:
        assert _resolve_py_type("SMALLMONEY") is float

    def test_uniqueidentifier(self) -> None:
        assert _resolve_py_type("UNIQUEIDENTIFIER") is str

    def test_unknown_type_falls_back_to_str(self) -> None:
        """Unknown types default to str with a warning."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _resolve_py_type("HIERARCHYID")
            assert result is str
            assert len(w) == 1
            assert "HIERARCHYID" in str(w[0].message)

    def test_case_insensitivity(self) -> None:
        """Type lookup is case-insensitive."""
        assert _resolve_py_type("varchar(255)") is str
        assert _resolve_py_type("Int") is int
        assert _resolve_py_type("datetime") is datetime

    def test_type_with_spaces(self) -> None:
        """Type names with extra spaces or qualifiers are handled."""
        assert _resolve_py_type("NVARCHAR (MAX)") is str
