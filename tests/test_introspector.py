"""Tests for SQLServerIntrospector facade — connect, detect_version, introspect."""

from unittest.mock import MagicMock, patch

import pytest

from singularity.introspector import SQLServerIntrospector
from singularity.types import SPMetadata
from singularity.version import ServerVersion


class TestConnect:
    """SQLServerIntrospector.connect() establishes a pyodbc connection."""

    def test_connect_success(self) -> None:
        """A valid connection string returns a Connection."""
        mock_conn = MagicMock()
        mock_pyodbc = MagicMock()
        mock_pyodbc.connect.return_value = mock_conn

        with patch.dict("sys.modules", {"pyodbc": mock_pyodbc}):
            introspector = SQLServerIntrospector(
                "DRIVER={ODBC Driver 18};SERVER=localhost"
            )
            result = introspector.connect()

        assert result is mock_conn
        assert introspector._connection is mock_conn

    def test_connect_failure(self) -> None:
        """A bad connection string raises ConnectionError."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.Error = Exception
        mock_pyodbc.connect.side_effect = Exception("Login failed")

        with patch.dict("sys.modules", {"pyodbc": mock_pyodbc}):
            introspector = SQLServerIntrospector("bad_conn_str")
            with pytest.raises(ConnectionError, match="Login failed"):
                introspector.connect()

        assert introspector._connection is None


class TestDetectVersion:
    """SQLServerIntrospector.detect_version() parses @@VERSION output."""

    @staticmethod
    def _make_introspector(version_output: str) -> SQLServerIntrospector:
        """Helper: create an introspector with a mock connection."""
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [version_output]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc = MagicMock()
        mock_pyodbc.connect.return_value = mock_conn

        with patch.dict("sys.modules", {"pyodbc": mock_pyodbc}):
            introspector = SQLServerIntrospector("conn_str")
            introspector.connect()
        return introspector

    def test_detect_modern(self, modern_version_string: str) -> None:
        """SQL Server 2022 → MODERN."""
        introspector = self._make_introspector(modern_version_string)
        version = introspector.detect_version()
        assert version == ServerVersion.MODERN

    def test_detect_legacy(self, legacy_version_string: str) -> None:
        """SQL Server 2012 → LEGACY."""
        introspector = self._make_introspector(legacy_version_string)
        version = introspector.detect_version()
        assert version == ServerVersion.LEGACY

    def test_detect_azure(self, azure_version_string: str) -> None:
        """Azure SQL Database → AZURE."""
        introspector = self._make_introspector(azure_version_string)
        version = introspector.detect_version()
        assert version == ServerVersion.AZURE

    def test_detect_not_connected(self) -> None:
        """detect_version() without connect() raises RuntimeError."""
        introspector = SQLServerIntrospector("conn_str")
        with pytest.raises(RuntimeError, match="Not connected"):
            introspector.detect_version()


class TestIntrospect:
    """SQLServerIntrospector.introspect() orchestrates version detection + strategy."""

    def test_introspect_auto_connects_and_detects(self) -> None:
        """introspect() calls connect() and detect_version() if not connected."""
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = mock_cursor
        # The strategy is mocked, so the cursor is only used by detect_version()
        mock_cursor.fetchone.return_value = [
            "Microsoft SQL Server 2022 (RTM-CU14) - 16.0.4125.3",
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc = MagicMock()
        mock_pyodbc.connect.return_value = mock_conn

        # Mock strategy to return expected metadata
        mock_strategy = MagicMock()
        expected_meta = SPMetadata(name="usp_Test", parameters=[], result_sets=[])
        mock_strategy.introspect.return_value = expected_meta

        with (
            patch.dict("sys.modules", {"pyodbc": mock_pyodbc}),
            patch("singularity.introspector._select_strategy", return_value=mock_strategy),
        ):
            introspector = SQLServerIntrospector("conn_str")
            meta = introspector.introspect("usp_Test")

        assert meta == expected_meta
        mock_strategy.introspect.assert_called_once_with("usp_Test", mock_cursor)
