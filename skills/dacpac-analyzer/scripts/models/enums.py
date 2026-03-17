"""Enumeration types for dacpac/bacpac domain models."""

from __future__ import annotations

from enum import Enum, IntEnum, unique


@unique
class ElementType(Enum):
    """Known model.xml element types.

    Use `from_type_string` to resolve a model.xml `Type` attribute value
    to an enum member, falling back to UNKNOWN for unrecognized types.
    """

    DATABASE_OPTIONS = "SqlDatabaseOptions"
    SCHEMA = "SqlSchema"
    TABLE = "SqlTable"
    VIEW = "SqlView"
    PROCEDURE = "SqlProcedure"
    SCALAR_FUNCTION = "SqlScalarFunction"
    INLINE_TVF = "SqlInlineTableValuedFunction"
    SEQUENCE = "SqlSequence"
    TABLE_TYPE = "SqlTableType"
    ROLE = "SqlRole"
    PERMISSION = "SqlPermissionStatement"
    FILEGROUP = "SqlFilegroup"
    PARTITION_FUNCTION = "SqlPartitionFunction"
    PARTITION_SCHEME = "SqlPartitionScheme"
    SIMPLE_COLUMN = "SqlSimpleColumn"
    COMPUTED_COLUMN = "SqlComputedColumn"
    TABLE_TYPE_COLUMN = "SqlTableTypeSimpleColumn"
    PRIMARY_KEY = "SqlPrimaryKeyConstraint"
    UNIQUE_CONSTRAINT = "SqlUniqueConstraint"
    FOREIGN_KEY = "SqlForeignKeyConstraint"
    CHECK_CONSTRAINT = "SqlCheckConstraint"
    DEFAULT_CONSTRAINT = "SqlDefaultConstraint"
    INDEX = "SqlIndex"
    COLUMNSTORE_INDEX = "SqlColumnStoreIndex"
    EXTENDED_PROPERTY = "SqlExtendedProperty"
    SUBROUTINE_PARAMETER = "SqlSubroutineParameter"
    UNKNOWN = "__unknown__"

    @classmethod
    def from_type_string(cls, type_string: str) -> ElementType:
        """Resolve a model.xml Type attribute value to an ElementType member.

        Returns UNKNOWN for any unrecognized type string.
        """
        try:
            return cls(type_string)
        except ValueError:
            return cls.UNKNOWN


# Pre-compute reverse lookup to validate the mapping is 1:1
_TYPE_VALUES = [m.value for m in ElementType if m is not ElementType.UNKNOWN]
assert len(_TYPE_VALUES) == len(set(_TYPE_VALUES)), "Duplicate ElementType values detected"


@unique
class SortOrder(Enum):
    """Column sort direction in indexes and constraints."""

    ASCENDING = "Ascending"
    DESCENDING = "Descending"


@unique
class CompressionLevel(IntEnum):
    """Data compression levels."""

    NONE = 0
    ROW = 1
    PAGE = 2


@unique
class PartitionRange(IntEnum):
    """Partition function range type."""

    LEFT = 1
    RIGHT = 2


@unique
class Durability(IntEnum):
    """Memory-optimized table durability."""

    SCHEMA_AND_DATA = 0
    SCHEMA_ONLY = 1


@unique
class PackageFormat(Enum):
    """Distinguishes schema-only (dacpac) from schema+data (bacpac) packages."""

    DACPAC = "dacpac"
    BACPAC = "bacpac"
