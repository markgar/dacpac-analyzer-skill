"""Element extractors for model.xml element types.

Each extractor handles one specific element type and produces
typed domain model instances. Extractors are registered with
an ``ExtractorRegistry`` for dispatch during parsing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from parsing.extractors.column_helpers import (
    extract_columns,
    extract_compression_options,
    extract_computed_column,
    extract_function_body,
    extract_indexed_columns,
    extract_parameters,
    extract_primary_key,
    extract_simple_column,
)
from parsing.extractors.constraints import (
    SqlCheckConstraintExtractor,
    SqlDefaultConstraintExtractor,
    SqlForeignKeyConstraintExtractor,
    SqlPrimaryKeyConstraintExtractor,
    SqlUniqueConstraintExtractor,
)
from parsing.extractors.database_options import (
    SqlDatabaseOptionsExtractor,
)
from parsing.extractors.filegroup import SqlFilegroupExtractor
from parsing.extractors.indexes import (
    SqlColumnStoreIndexExtractor,
    SqlIndexExtractor,
)
from parsing.extractors.partition_function import (
    SqlPartitionFunctionExtractor,
)
from parsing.extractors.partition_scheme import (
    SqlPartitionSchemeExtractor,
)
from parsing.extractors.inline_tvf import (
    SqlInlineTableValuedFunctionExtractor,
)
from parsing.extractors.procedure import SqlProcedureExtractor
from parsing.extractors.scalar_function import SqlScalarFunctionExtractor
from parsing.extractors.extended_property import (
    SqlExtendedPropertyExtractor,
)
from parsing.extractors.permission import (
    SqlPermissionStatementExtractor,
)
from parsing.extractors.role import SqlRoleExtractor
from parsing.extractors.schema import SqlSchemaExtractor
from parsing.extractors.sequence import SqlSequenceExtractor
from parsing.extractors.table import SqlTableExtractor
from parsing.extractors.table_type import SqlTableTypeExtractor
from parsing.extractors.view import SqlViewExtractor

if TYPE_CHECKING:
    from parsing.registry import ExtractorRegistry

__all__ = [
    "SqlCheckConstraintExtractor",
    "SqlColumnStoreIndexExtractor",
    "SqlDatabaseOptionsExtractor",
    "SqlDefaultConstraintExtractor",
    "SqlExtendedPropertyExtractor",
    "SqlFilegroupExtractor",
    "SqlForeignKeyConstraintExtractor",
    "SqlIndexExtractor",
    "SqlInlineTableValuedFunctionExtractor",
    "SqlPartitionFunctionExtractor",
    "SqlPartitionSchemeExtractor",
    "SqlPermissionStatementExtractor",
    "SqlPrimaryKeyConstraintExtractor",
    "SqlProcedureExtractor",
    "SqlRoleExtractor",
    "SqlScalarFunctionExtractor",
    "SqlSchemaExtractor",
    "SqlSequenceExtractor",
    "SqlTableExtractor",
    "SqlTableTypeExtractor",
    "SqlUniqueConstraintExtractor",
    "SqlViewExtractor",
    "extract_columns",
    "extract_compression_options",
    "extract_computed_column",
    "extract_function_body",
    "extract_indexed_columns",
    "extract_parameters",
    "extract_primary_key",
    "extract_simple_column",
    "register_spec05_extractors",
    "register_spec06_extractors",
    "register_spec07_extractors",
    "register_spec08_extractors",
    "register_spec09_extractors",
]


def register_spec05_extractors(registry: ExtractorRegistry) -> None:
    """Register all Spec 05 element extractors with the given registry.

    Registers extractors for:
    - ``SqlDatabaseOptions``
    - ``SqlSchema``
    - ``SqlFilegroup``
    - ``SqlPartitionFunction``
    - ``SqlPartitionScheme``
    """
    registry.register(SqlDatabaseOptionsExtractor())
    registry.register(SqlSchemaExtractor())
    registry.register(SqlFilegroupExtractor())
    registry.register(SqlPartitionFunctionExtractor())
    registry.register(SqlPartitionSchemeExtractor())


def register_spec06_extractors(registry: ExtractorRegistry) -> None:
    """Register all Spec 06 element extractors with the given registry.

    Registers extractors for:
    - ``SqlTable`` (columns are extracted inline within the table)
    """
    registry.register(SqlTableExtractor())


def register_spec07_extractors(registry: ExtractorRegistry) -> None:
    """Register all Spec 07 element extractors with the given registry.

    Registers extractors for:
    - ``SqlPrimaryKeyConstraint``
    - ``SqlUniqueConstraint``
    - ``SqlForeignKeyConstraint``
    - ``SqlCheckConstraint``
    - ``SqlDefaultConstraint``
    - ``SqlIndex``
    - ``SqlColumnStoreIndex``
    """
    registry.register(SqlPrimaryKeyConstraintExtractor())
    registry.register(SqlUniqueConstraintExtractor())
    registry.register(SqlForeignKeyConstraintExtractor())
    registry.register(SqlCheckConstraintExtractor())
    registry.register(SqlDefaultConstraintExtractor())
    registry.register(SqlIndexExtractor())
    registry.register(SqlColumnStoreIndexExtractor())


def register_spec08_extractors(registry: ExtractorRegistry) -> None:
    """Register all Spec 08 element extractors with the given registry.

    Registers extractors for:
    - ``SqlProcedure``
    - ``SqlScalarFunction``
    - ``SqlInlineTableValuedFunction``
    """
    registry.register(SqlProcedureExtractor())
    registry.register(SqlScalarFunctionExtractor())
    registry.register(SqlInlineTableValuedFunctionExtractor())


def register_spec09_extractors(registry: ExtractorRegistry) -> None:
    """Register all Spec 09 element extractors with the given registry.

    Registers extractors for:
    - ``SqlRole``
    - ``SqlPermissionStatement``
    - ``SqlSequence``
    - ``SqlTableType``
    - ``SqlView``
    - ``SqlExtendedProperty``
    """
    registry.register(SqlRoleExtractor())
    registry.register(SqlPermissionStatementExtractor())
    registry.register(SqlSequenceExtractor())
    registry.register(SqlTableTypeExtractor())
    registry.register(SqlViewExtractor())
    registry.register(SqlExtendedPropertyExtractor())

