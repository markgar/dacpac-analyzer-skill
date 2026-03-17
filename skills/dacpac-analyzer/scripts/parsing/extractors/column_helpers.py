"""Reusable helpers for extracting column, parameter, function body, and compression option models.

Handles ``SqlSimpleColumn``, ``SqlComputedColumn``,
``SqlDataCompressionOption``, ``SqlIndexedColumnSpecification``,
``SqlSubroutineParameter``, and ``SqlScriptFunctionImplementation``
inline elements found within table, constraint, index, procedure,
and function relationships.
"""

from __future__ import annotations

import logging
from xml.etree.ElementTree import Element

from models.domain import (
    Column,
    DataCompressionOption,
    IndexedColumn,
    Parameter,
    PrimaryKey,
)
from models.enums import CompressionLevel, SortOrder
from models.parsed_name import ParsedName
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    extract_type_specifier,
    get_cdata_property,
    get_relationship_inline_elements,
    get_relationship_references,
    get_simple_property,
)

logger = logging.getLogger(__name__)

_SIMPLE_COLUMN_TYPE = "SqlSimpleColumn"
_TABLE_TYPE_SIMPLE_COLUMN_TYPE = "SqlTableTypeSimpleColumn"
_COMPUTED_COLUMN_TYPE = "SqlComputedColumn"


def extract_simple_column(element: Element, ordinal: int) -> Column | None:
    """Extract a ``Column`` from a ``SqlSimpleColumn`` element.

    Returns ``None`` if the element has no valid Name attribute.
    ``IsNullable`` defaults to ``True`` when the property is absent.
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlSimpleColumn with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlSimpleColumn with malformed Name: %r", name_attr
        )
        return None

    # IsNullable defaults to True when absent (spec §5)
    nullable_val = get_simple_property(element, "IsNullable")
    is_nullable = nullable_val is None or nullable_val.lower() != "false"

    type_spec = extract_type_specifier(element)
    if type_spec is None:
        logger.warning(
            "SqlSimpleColumn %r has no TypeSpecifier", name_attr
        )

    generated_always_type = get_simple_property(element, "GeneratedAlwaysType")

    return Column(
        name=parsed_name,
        ordinal=ordinal,
        type_specifier=type_spec,
        is_nullable=is_nullable,
        is_computed=False,
        expression_script=None,
        is_persisted=False,
        generated_always_type=generated_always_type,
    )


def extract_computed_column(element: Element, ordinal: int) -> Column | None:
    """Extract a ``Column`` from a ``SqlComputedColumn`` element.

    Returns ``None`` if the element has no valid Name attribute.
    When the ``TypeSpecifier`` relationship is absent, a sentinel
    ``TypeSpecifier`` is used — the type is derived from the expression.
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlComputedColumn with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlComputedColumn with malformed Name: %r", name_attr
        )
        return None

    cdata_result = get_cdata_property(element, "ExpressionScript")
    expression_script = cdata_result.text if cdata_result is not None else None

    persisted_val = get_simple_property(element, "IsPersisted")
    is_persisted = persisted_val is not None and persisted_val.lower() == "true"

    type_spec = extract_type_specifier(element)
    if type_spec is None:
        logger.debug(
            "SqlComputedColumn %r has no TypeSpecifier — derived from expression",
            name_attr,
        )

    return Column(
        name=parsed_name,
        ordinal=ordinal,
        type_specifier=type_spec,
        is_nullable=True,
        is_computed=True,
        expression_script=expression_script,
        is_persisted=is_persisted,
        generated_always_type=None,
    )


def extract_columns(column_elements: tuple[Element, ...]) -> tuple[Column, ...]:
    """Extract ``Column`` models from inline column elements in document order.

    Dispatches to the appropriate extractor based on the element ``Type``
    attribute. Ordinals are zero-based and assigned sequentially to
    successfully extracted columns.
    """
    columns: list[Column] = []
    ordinal = 0

    for element in column_elements:
        type_str = element.get("Type")

        if type_str in (_SIMPLE_COLUMN_TYPE, _TABLE_TYPE_SIMPLE_COLUMN_TYPE):
            column = extract_simple_column(element, ordinal)
        elif type_str == _COMPUTED_COLUMN_TYPE:
            column = extract_computed_column(element, ordinal)
        else:
            logger.warning("Unknown column type %r — skipping", type_str)
            continue

        if column is not None:
            columns.append(column)
            ordinal += 1

    return tuple(columns)


def extract_compression_options(
    element: Element,
) -> tuple[DataCompressionOption, ...]:
    """Extract ``DataCompressionOption`` models from a parent element.

    Reads inline ``SqlDataCompressionOption`` elements from the
    ``DataCompressionOptions`` relationship.
    """
    inline_elements = get_relationship_inline_elements(
        element, "DataCompressionOptions"
    )
    options: list[DataCompressionOption] = []

    for opt_elem in inline_elements:
        compression_val = get_simple_property(opt_elem, "CompressionLevel")
        partition_val = get_simple_property(opt_elem, "PartitionNumber")

        compression_level = CompressionLevel.NONE
        if compression_val is not None:
            try:
                compression_level = CompressionLevel(int(compression_val))
            except (ValueError, KeyError):
                logger.warning(
                    "Malformed CompressionLevel value: %r — defaulting to NONE",
                    compression_val,
                )

        partition_number: int | None = None
        if partition_val is not None:
            try:
                partition_number = int(partition_val)
            except ValueError:
                logger.warning(
                    "Malformed PartitionNumber value: %r — skipping",
                    partition_val,
                )

        options.append(
            DataCompressionOption(
                compression_level=compression_level,
                partition_number=partition_number,
            )
        )

    return tuple(options)


def extract_indexed_columns(element: Element) -> tuple[IndexedColumn, ...]:
    """Extract indexed column specifications from a ColumnSpecifications relationship.

    Reads ``SqlIndexedColumnSpecification`` inline elements in document order.
    Each specification has a ``Column`` relationship (ref) and an optional
    ``IsDescending`` property. Returns columns in document order — this
    determines key order.
    """
    spec_elements = get_relationship_inline_elements(element, "ColumnSpecifications")
    results: list[IndexedColumn] = []

    for spec_elem in spec_elements:
        col_refs = get_relationship_references(spec_elem, "Column")
        if not col_refs:
            logger.warning(
                "SqlIndexedColumnSpecification has no Column reference — skipping"
            )
            continue

        column_ref = col_refs[0]

        is_desc_val = get_simple_property(spec_elem, "IsDescending")
        if is_desc_val is not None and is_desc_val.lower() == "true":
            sort_order = SortOrder.DESCENDING
        else:
            sort_order = SortOrder.ASCENDING

        results.append(IndexedColumn(column_ref=column_ref, sort_order=sort_order))

    return tuple(results)


_SUBROUTINE_PARAMETER_TYPE = "SqlSubroutineParameter"


def extract_parameters(element: Element) -> tuple[Parameter, ...]:
    """Extract ``Parameter`` models from inline ``SqlSubroutineParameter`` elements.

    Reads the ``Parameters`` relationship from the parent element and
    returns parameters in document order — ordinal position matters for
    positional calling.

    Parameters whose ``TypeSpecifier`` is missing are skipped with a
    warning, since ``Parameter.type_specifier`` is a required field.
    """
    param_elements = get_relationship_inline_elements(element, "Parameters")
    parameters: list[Parameter] = []

    for param_elem in param_elements:
        param_type = param_elem.get("Type")
        if param_type != _SUBROUTINE_PARAMETER_TYPE:
            logger.warning("Unexpected parameter type %r — skipping", param_type)
            continue

        name_attr = param_elem.get("Name")
        if name_attr is None:
            logger.warning("Skipping SqlSubroutineParameter with no Name attribute")
            continue

        try:
            parsed_name = parse_name(name_attr)
        except ValueError:
            logger.warning(
                "Skipping SqlSubroutineParameter with malformed Name: %r",
                name_attr,
            )
            continue

        is_output_val = get_simple_property(param_elem, "IsOutput")
        is_output = is_output_val is not None and is_output_val.lower() == "true"

        type_spec = extract_type_specifier(param_elem, relationship_name="Type")
        if type_spec is None:
            logger.warning(
                "SqlSubroutineParameter %r has no TypeSpecifier — skipping",
                name_attr,
            )
            continue

        parameters.append(
            Parameter(
                name=parsed_name,
                type_specifier=type_spec,
                is_output=is_output,
            )
        )

    return tuple(parameters)


_FUNCTION_IMPLEMENTATION_TYPE = "SqlScriptFunctionImplementation"


def extract_function_body(
    element: Element,
) -> tuple[str, tuple[ParsedName, ...]]:
    """Extract function body script and dependencies from a ``FunctionBody`` relationship.

    Navigates the nested pattern::

        FunctionBody relationship
          └─ SqlScriptFunctionImplementation (inline element)
               └─ BodyScript CDATA property
               └─ BodyDependencies relationship

    Returns a ``(body_script, body_dependencies)`` tuple.  When the
    ``FunctionBody`` relationship or its implementation element is absent,
    returns ``("", ())``.
    """
    impl_elements = get_relationship_inline_elements(element, "FunctionBody")
    if not impl_elements:
        return ("", ())

    for impl_elem in impl_elements:
        impl_type = impl_elem.get("Type")
        if impl_type != _FUNCTION_IMPLEMENTATION_TYPE:
            logger.warning(
                "Unexpected FunctionBody implementation type %r — skipping",
                impl_type,
            )
            continue

        body_result = get_cdata_property(impl_elem, "BodyScript")
        body_script = body_result.text if body_result is not None else ""

        body_dependencies = get_relationship_references(impl_elem, "BodyDependencies")

        return (body_script, body_dependencies)

    return ("", ())


def extract_primary_key(element: Element) -> PrimaryKey | None:
    """Extract a ``PrimaryKey`` from a primary key constraint element.

    Shared helper used by both ``SqlPrimaryKeyConstraint`` (top-level)
    and ``SqlTableTypePrimaryKeyConstraint`` (inline within table types).

    Returns ``None`` if the element is missing required fields (Name,
    DefiningTable).
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping primary key constraint element with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping primary key constraint with malformed Name: %r", name_attr
        )
        return None

    defining_refs = get_relationship_references(element, "DefiningTable")
    if not defining_refs:
        logger.warning(
            "Primary key constraint %r has no DefiningTable — skipping", name_attr
        )
        return None
    defining_table = defining_refs[0]

    columns = extract_indexed_columns(element)

    fg_refs = get_relationship_references(element, "Filegroup")
    filegroup = fg_refs[0] if fg_refs else None

    return PrimaryKey(
        name=parsed_name,
        defining_table=defining_table,
        columns=columns,
        filegroup=filegroup,
    )
