"""Core domain models for dacpac/bacpac database objects.

All models are frozen dataclasses — immutable after construction.
List fields use tuples for immutability; optional fields default to None.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models.enums import (
    CompressionLevel,
    Durability,
    PartitionRange,
    SortOrder,
)
from models.parsed_name import ParsedName


@dataclass(frozen=True, slots=True)
class TypeSpecifier:
    """Data type details for a column, parameter, or return type."""

    type_name: str
    is_builtin: bool
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    is_max: bool = False


@dataclass(frozen=True, slots=True)
class Column:
    """Table or view column."""

    name: ParsedName
    ordinal: int
    type_specifier: TypeSpecifier | None = None
    is_nullable: bool = True
    is_computed: bool = False
    expression_script: str | None = None
    is_persisted: bool = False
    generated_always_type: str | None = None


@dataclass(frozen=True, slots=True)
class IndexedColumn:
    """A column reference within an index or constraint, with sort direction."""

    column_ref: ParsedName
    sort_order: SortOrder = SortOrder.ASCENDING


@dataclass(frozen=True, slots=True)
class PrimaryKey:
    """Primary key constraint."""

    name: ParsedName
    defining_table: ParsedName
    columns: tuple[IndexedColumn, ...] = ()
    filegroup: ParsedName | None = None


@dataclass(frozen=True, slots=True)
class UniqueConstraint:
    """Unique constraint — same shape as PrimaryKey."""

    name: ParsedName
    defining_table: ParsedName
    columns: tuple[IndexedColumn, ...] = ()
    filegroup: ParsedName | None = None


@dataclass(frozen=True, slots=True)
class ForeignKey:
    """Foreign key constraint."""

    name: ParsedName
    defining_table: ParsedName
    foreign_table: ParsedName
    columns: tuple[ParsedName, ...] = ()
    foreign_columns: tuple[ParsedName, ...] = ()


@dataclass(frozen=True, slots=True)
class CheckConstraint:
    """Check constraint."""

    name: ParsedName
    defining_table: ParsedName
    expression: str = ""


@dataclass(frozen=True, slots=True)
class DefaultConstraint:
    """Default constraint."""

    name: ParsedName
    defining_table: ParsedName
    for_column: ParsedName
    expression: str = ""


@dataclass(frozen=True, slots=True)
class Index:
    """Table or view index."""

    name: ParsedName
    indexed_object: ParsedName
    columns: tuple[IndexedColumn, ...] = ()
    filegroup: ParsedName | None = None
    is_columnstore: bool = False


@dataclass(frozen=True, slots=True)
class DataCompressionOption:
    """Data compression setting for a table or partition."""

    compression_level: CompressionLevel = CompressionLevel.NONE
    partition_number: int | None = None


@dataclass(frozen=True, slots=True)
class Table:
    """Database table."""

    name: ParsedName
    schema_ref: ParsedName
    columns: tuple[Column, ...] = ()
    is_memory_optimized: bool = False
    durability: Durability | None = None
    is_ansi_nulls_on: bool = True
    filegroup: ParsedName | None = None
    lob_filegroup: ParsedName | None = None
    temporal_history_table: ParsedName | None = None
    compression_options: tuple[DataCompressionOption, ...] = ()


@dataclass(frozen=True, slots=True)
class View:
    """Database view."""

    name: ParsedName
    schema_ref: ParsedName
    columns: tuple[Column, ...] = ()
    query_script: str = ""


@dataclass(frozen=True, slots=True)
class Parameter:
    """Stored procedure or function parameter."""

    name: ParsedName
    type_specifier: TypeSpecifier
    is_output: bool = False


@dataclass(frozen=True, slots=True)
class Procedure:
    """Stored procedure."""

    name: ParsedName
    schema_ref: ParsedName
    parameters: tuple[Parameter, ...] = ()
    body_script: str = ""
    body_dependencies: tuple[ParsedName, ...] = ()
    is_ansi_nulls_on: bool = True
    is_quoted_identifiers_on: bool = True
    execute_as: str | None = None


@dataclass(frozen=True, slots=True)
class ScalarFunction:
    """Scalar user-defined function."""

    name: ParsedName
    schema_ref: ParsedName
    return_type: TypeSpecifier
    parameters: tuple[Parameter, ...] = ()
    body_script: str = ""
    body_dependencies: tuple[ParsedName, ...] = ()


@dataclass(frozen=True, slots=True)
class InlineTableValuedFunction:
    """Inline table-valued function."""

    name: ParsedName
    schema_ref: ParsedName
    parameters: tuple[Parameter, ...] = ()
    columns: tuple[Column, ...] = ()
    body_script: str = ""
    body_dependencies: tuple[ParsedName, ...] = ()


@dataclass(frozen=True, slots=True)
class Sequence:
    """Database sequence."""

    name: ParsedName
    schema_ref: ParsedName
    type_specifier: TypeSpecifier
    start_value: str = "0"
    increment: str = "1"
    current_value: str | None = None


@dataclass(frozen=True, slots=True)
class TableType:
    """User-defined table type."""

    name: ParsedName
    schema_ref: ParsedName
    columns: tuple[Column, ...] = ()
    primary_key: PrimaryKey | None = None


@dataclass(frozen=True, slots=True)
class Role:
    """Database role."""

    name: ParsedName
    authorizer: ParsedName


@dataclass(frozen=True, slots=True)
class Permission:
    """Permission statement."""

    permission_code: str
    grantee: ParsedName
    name: ParsedName | None = None
    secured_object: ParsedName | None = None


@dataclass(frozen=True, slots=True)
class Schema:
    """Database schema."""

    name: ParsedName
    authorizer: ParsedName


@dataclass(frozen=True, slots=True)
class Filegroup:
    """Database filegroup."""

    name: ParsedName
    contains_memory_optimized_data: bool = False


@dataclass(frozen=True, slots=True)
class PartitionFunction:
    """Partition function."""

    name: ParsedName
    parameter_type: TypeSpecifier
    range_type: PartitionRange = PartitionRange.LEFT
    boundary_values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PartitionScheme:
    """Partition scheme."""

    name: ParsedName
    partition_function: ParsedName
    filegroups: tuple[ParsedName, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtendedProperty:
    """Extended property on a database object."""

    name: ParsedName
    host: ParsedName
    value: str = ""


@dataclass(frozen=True, slots=True)
class DatabaseOptions:
    """Database-level configuration options.

    Uses a frozenset of key-value pairs for immutability instead of a dict,
    with a helper property to reconstruct a dict when needed.
    """

    _properties: tuple[tuple[str, str], ...] = ()
    collation_lcid: str | None = None
    collation_case_sensitive: str | None = None

    @property
    def properties(self) -> dict[str, str]:
        """Return properties as a dict (read-only view)."""
        return dict(self._properties)
