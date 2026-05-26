"""Singularity — SQL Server stored procedure introspection and Pydantic model generation."""

from singularity.exceptions import SingularityError, SpNotFoundError
from singularity.introspector import SQLServerIntrospector
from singularity.model_generator import generate_model
from singularity.types import ColumnInfo, Parameter, SPMetadata
from singularity.version import ServerVersion

__all__ = [
    "SQLServerIntrospector",
    "generate_model",
    "SPMetadata",
    "ColumnInfo",
    "Parameter",
    "ServerVersion",
    "SingularityError",
    "SpNotFoundError",
]
