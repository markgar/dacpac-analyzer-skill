"""Extractor for SqlTableType elements.

Parses user-defined table types with columns and optional primary key
constraint from each ``SqlTableType`` element in model.xml.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import PrimaryKey, TableType
from parsing.extractors.column_helpers import (
    extract_columns,
    extract_primary_key,
)
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    get_relationship_inline_elements,
    get_relationship_references,
)

logger = logging.getLogger(__name__)

_TABLE_TYPE_PK_TYPE = "SqlTableTypePrimaryKeyConstraint"


class SqlTableTypeExtractor(ElementExtractor):
    """Extract ``TableType`` domain models from ``SqlTableType`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlTableType"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[TableType, ...]:
        """Extract table types with columns and optional primary key."""
        results: list[TableType] = []
        for element in elements:
            tt = _extract_single_table_type(element)
            if tt is not None:
                results.append(tt)
        return tuple(results)


def _extract_single_table_type(element: Element) -> TableType | None:
    """Extract a single ``TableType`` from a ``SqlTableType`` element.

    Returns ``None`` if the element has no valid Name attribute or is
    missing the required Schema relationship.
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlTableType element with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlTableType with malformed Name: %r", name_attr
        )
        return None

    # Schema relationship (required)
    schema_refs = get_relationship_references(element, "Schema")
    if not schema_refs:
        logger.warning(
            "SqlTableType %r has no Schema relationship — skipping", name_attr
        )
        return None
    schema_ref = schema_refs[0]

    # Columns from inline elements (SqlTableTypeSimpleColumn)
    column_elements = get_relationship_inline_elements(element, "Columns")
    columns = extract_columns(column_elements)

    # Primary key from inline constraint element
    primary_key = _extract_inline_primary_key(element)

    return TableType(
        name=parsed_name,
        schema_ref=schema_ref,
        columns=columns,
        primary_key=primary_key,
    )


def _extract_inline_primary_key(element: Element) -> PrimaryKey | None:
    """Extract a ``PrimaryKey`` from an inline ``SqlTableTypePrimaryKeyConstraint``.

    Searches the ``Constraints`` relationship for an element with
    ``Type="SqlTableTypePrimaryKeyConstraint"`` and delegates to the
    shared ``extract_primary_key`` helper.

    Returns ``None`` if no primary key constraint is found.
    """
    constraint_elements = get_relationship_inline_elements(element, "Constraints")
    for constraint_elem in constraint_elements:
        if constraint_elem.get("Type") == _TABLE_TYPE_PK_TYPE:
            return extract_primary_key(constraint_elem)
    return None
