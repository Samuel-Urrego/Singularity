"""SQL Server stored procedure introspector — facade over version-specific strategies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from singularity.types import SPMetadata
from singularity.version import (
    ServerVersion,
    _select_strategy,
    parse_version_string,
)

if TYPE_CHECKING:
    import pyodbc


class SQLServerIntrospector:
    """Facade for introspecting SQL Server stored procedures.

    Manages a pyodbc connection, auto-detects the SQL Server version,
    and delegates to the appropriate version-specific introspection strategy.

    Usage:
        introspector = SQLServerIntrospector("DRIVER={ODBC Driver 18};SERVER=...")
        introspector.connect()
        meta = introspector.introspect("usp_GetOrders")
    """

    def __init__(self, conn_str: str) -> None:
        """Initialise the introspector with a connection string.

        Args:
            conn_str: A pyodbc-compatible connection string.
        """
        self._conn_str: str = conn_str
        self._connection: pyodbc.Connection | None = None
        self._version: ServerVersion | None = None
        self._strategy: object | None = None

    def connect(self) -> object:
        """Establish a connection to SQL Server.

        Returns:
            The pyodbc Connection object.

        Raises:
            ConnectionError: If the connection fails.
        """
        import pyodbc

        try:
            conn = pyodbc.connect(self._conn_str, autocommit=True)
        except pyodbc.Error as exc:
            raise ConnectionError(
                f"Failed to connect to SQL Server: {exc}"
            ) from exc

        self._connection = conn
        return conn

    def detect_version(self) -> ServerVersion:
        """Detect the SQL Server version by querying @@VERSION.

        Returns:
            A ServerVersion enum value.

        Raises:
            RuntimeError: If not connected.
        """
        if self._connection is None:
            raise RuntimeError(
                "Not connected. Call connect() before detect_version()."
            )

        cursor = self._connection.cursor()
        cursor.execute("SELECT @@VERSION")
        version_output: str = cursor.fetchone()[0]

        self._version = parse_version_string(version_output)
        return self._version

    def introspect(self, sp_name: str) -> SPMetadata:
        """Introspect a stored procedure and return its metadata.

        Calls connect() and detect_version() automatically if not yet connected.

        Args:
            sp_name: The stored procedure name (with or without schema prefix).

        Returns:
            SPMetadata containing parameter and result set column info.

        Raises:
            SpNotFoundError: If the procedure does not exist.
            ConnectionError: If connection fails.
        """
        if self._connection is None:
            self.connect()
        assert self._connection is not None  # narrowed by connect()

        if self._version is None:
            self.detect_version()
        assert self._version is not None  # narrowed by detect_version()

        cursor = self._connection.cursor()
        strategy = _select_strategy(self._version)
        return strategy.introspect(sp_name, cursor)
