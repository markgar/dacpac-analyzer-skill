"""Aggregate and package-level models.

DatabaseModel holds the complete parsed result of a package.
PackageMetadata, PackageOrigin, and Package represent package-level data.
All models are frozen dataclasses — immutable after construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from models.enums import PackageFormat
from models.domain import (
    CheckConstraint,
    DatabaseOptions,
    DefaultConstraint,
    ExtendedProperty,
    Filegroup,
    ForeignKey,
    Index,
    InlineTableValuedFunction,
    PartitionFunction,
    PartitionScheme,
    Permission,
    PrimaryKey,
    Procedure,
    Role,
    ScalarFunction,
    Schema,
    Sequence,
    Table,
    TableType,
    UniqueConstraint,
    View,
)


@dataclass(frozen=True, slots=True)
class DatabaseModel:
    """Complete parsed result of a dacpac/bacpac model.xml.

    All collection fields default to empty tuples so downstream consumers
    never need null checks — a zero-element DatabaseModel is always valid.
    """

    database_options: DatabaseOptions | None = None
    schemas: tuple[Schema, ...] = ()
    tables: tuple[Table, ...] = ()
    views: tuple[View, ...] = ()
    procedures: tuple[Procedure, ...] = ()
    scalar_functions: tuple[ScalarFunction, ...] = ()
    inline_tvfs: tuple[InlineTableValuedFunction, ...] = ()
    sequences: tuple[Sequence, ...] = ()
    table_types: tuple[TableType, ...] = ()
    roles: tuple[Role, ...] = ()
    permissions: tuple[Permission, ...] = ()
    filegroups: tuple[Filegroup, ...] = ()
    partition_functions: tuple[PartitionFunction, ...] = ()
    partition_schemes: tuple[PartitionScheme, ...] = ()
    primary_keys: tuple[PrimaryKey, ...] = ()
    unique_constraints: tuple[UniqueConstraint, ...] = ()
    foreign_keys: tuple[ForeignKey, ...] = ()
    check_constraints: tuple[CheckConstraint, ...] = ()
    default_constraints: tuple[DefaultConstraint, ...] = ()
    indexes: tuple[Index, ...] = ()
    extended_properties: tuple[ExtendedProperty, ...] = ()


@dataclass(frozen=True, slots=True)
class PackageMetadata:
    """Metadata from DacMetadata.xml."""

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class PackageOrigin:
    """Origin information from Origin.xml.

    Uses a tuple of key-value pairs for object_counts to maintain
    immutability, with a helper property for dict access.
    """

    contains_exported_data: bool = False
    server_version: str | None = None
    product_version: str | None = None
    _object_counts: tuple[tuple[str, int], ...] = ()
    source_database_size_kb: int | None = None
    total_row_count: int | None = None
    model_checksum: str | None = None
    model_schema_version: str | None = None
    export_timestamp: str | None = None

    @property
    def object_counts(self) -> dict[str, int]:
        """Return object counts as a dict (read-only view)."""
        return dict(self._object_counts)


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Raw content extracted from a dacpac/bacpac archive.

    Contains the raw bytes of each required file and a listing of
    all entries in the archive. No XML parsing is performed here.
    """

    format: PackageFormat
    model_xml: bytes
    dac_metadata_xml: bytes
    origin_xml: bytes
    file_list: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModelParseResult:
    """Result of parsing model.xml — bundles DatabaseModel with root attributes.

    Eliminates the need for mutable state on the parser: a single call to
    ``parse()`` returns everything the caller needs.
    """

    database_model: DatabaseModel
    format_version: str = ""
    schema_version: str = ""
    dsp_name: str = ""


@dataclass(frozen=True, slots=True)
class Package:
    """Top-level representation of a dacpac or bacpac package."""

    metadata: PackageMetadata
    origin: PackageOrigin
    database_model: DatabaseModel
    format_version: str
    schema_version: str
    dsp_name: str
