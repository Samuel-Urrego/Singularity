"""Pydantic v2 models for stored procedure metadata."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Parameter(BaseModel):
    """Metadata for a single stored procedure parameter."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Parameter name (e.g. '@OrderId')."""

    sql_type: str
    """SQL Server data type (e.g. 'INT', 'NVARCHAR(50)')."""

    direction: Literal["IN", "OUT", "INOUT"]
    """Parameter direction: input, output, or bidirectional."""

    default: str | None = None
    """Default value expression, or None if no default."""

    nullable: bool = True
    """Whether the parameter accepts NULL."""

    description: str | None = None
    """Parameter description from sys.extended_properties, or None."""


class ColumnInfo(BaseModel):
    """Metadata for a single result set column."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Column name as returned by SQL Server."""

    sql_type: str
    """SQL Server data type (e.g. 'INT', 'VARCHAR(100)')."""

    nullable: bool = True
    """Whether the column is nullable."""

    description: str | None = None
    """Column description from sys.extended_properties, or None."""


class SPMetadata(BaseModel):
    """Complete metadata for a stored procedure's parameters and result sets."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Stored procedure name (schema-qualified where available)."""

    parameters: list[Parameter] = []
    """List of parameter metadata objects."""

    result_sets: list[list[ColumnInfo]] = []
    """List of result sets, each being a list of ColumnInfo objects."""

    @property
    def columns(self) -> list[ColumnInfo]:
        """First result set columns (backward compatibility).

        Returns the column metadata for the first result set,
        or an empty list if there are no result sets.
        """
        return self.result_sets[0] if self.result_sets else []
