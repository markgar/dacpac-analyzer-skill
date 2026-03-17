"""Extractor for SqlTable elements.

Composes column and compression helpers to produce fully populated
``Table`` domain models from ``SqlTable`` elements in model.xml.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import Table
from models.enums import Durability
from parsing.extractors.column_helpers import (
    extract_columns,
    extract_compression_options,
)
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    get_relationship_inline_elements,
    get_relationship_references,
    get_simple_property,
)

logger = logging.getLogger(__name__)


class SqlTableExtractor(ElementExtractor):
    """Extract ``Table`` domain models from ``SqlTable`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlTable"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Table, ...]:
        """Extract tables with columns, compression options, and all properties."""
        results: list[Table] = []
        for element in elements:
            table = _extract_single_table(element)
            if table is not None:
                results.append(table)
        return tuple(results)


def _extract_single_table(element: Element) -> Table | None:
    """Extract a single ``Table`` from a ``SqlTable`` element.

    Returns ``None`` if the element has no valid Name attribute.
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlTable element with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning("Skipping SqlTable with malformed Name: %r", name_attr)
        return None

    # Schema relationship (required for tables, but degrade gracefully)
    schema_refs = get_relationship_references(element, "Schema")
    if not schema_refs:
        logger.warning("SqlTable %r has no Schema relationship — skipping", name_attr)
        return None
    schema_ref = schema_refs[0]

    # Boolean properties with defaults
    ansi_nulls_val = get_simple_property(element, "IsAnsiNullsOn")
    is_ansi_nulls_on = ansi_nulls_val is None or ansi_nulls_val.lower() != "false"

    mem_opt_val = get_simple_property(element, "IsMemoryOptimized")
    is_memory_optimized = mem_opt_val is not None and mem_opt_val.lower() == "true"

    # Durability enum
    durability = _parse_durability(get_simple_property(element, "Durability"))

    # Filegroup relationships
    fg_refs = get_relationship_references(element, "Filegroup")
    filegroup = fg_refs[0] if fg_refs else None

    lob_fg_refs = get_relationship_references(element, "FilegroupForTextImage")
    lob_filegroup = lob_fg_refs[0] if lob_fg_refs else None

    # Temporal history table
    temporal_refs = get_relationship_references(
        element, "TemporalSystemVersioningHistoryTable"
    )
    temporal_history_table = temporal_refs[0] if temporal_refs else None

    # Columns from inline elements
    column_elements = get_relationship_inline_elements(element, "Columns")
    columns = extract_columns(column_elements)

    # Compression options
    compression_options = extract_compression_options(element)

    return Table(
        name=parsed_name,
        schema_ref=schema_ref,
        columns=columns,
        is_memory_optimized=is_memory_optimized,
        durability=durability,
        is_ansi_nulls_on=is_ansi_nulls_on,
        filegroup=filegroup,
        lob_filegroup=lob_filegroup,
        temporal_history_table=temporal_history_table,
        compression_options=compression_options,
    )


def _parse_durability(raw_value: str | None) -> Durability | None:
    """Parse a Durability property value to the enum, or None if absent."""
    if raw_value is None:
        return None
    try:
        return Durability(int(raw_value))
    except (ValueError, KeyError):
        logger.warning(
            "Malformed Durability value: %r — treating as absent", raw_value
        )
        return None
