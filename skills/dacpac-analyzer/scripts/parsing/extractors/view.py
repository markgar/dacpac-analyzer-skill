"""Extractor for SqlView elements.

Parses view name, schema reference, query script, and computed columns
for each ``SqlView`` element in model.xml.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import View
from parsing.extractors.column_helpers import extract_columns
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    get_cdata_property,
    get_relationship_inline_elements,
    get_relationship_references,
)

logger = logging.getLogger(__name__)


class SqlViewExtractor(ElementExtractor):
    """Extract ``View`` domain models from ``SqlView`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlView"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[View, ...]:
        """Extract views with query script and computed columns."""
        results: list[View] = []
        for element in elements:
            view = _extract_single_view(element)
            if view is not None:
                results.append(view)
        return tuple(results)


def _extract_single_view(element: Element) -> View | None:
    """Extract a single ``View`` from a ``SqlView`` element.

    Returns ``None`` if the element has no valid Name attribute or is
    missing the required Schema relationship.
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlView element with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlView with malformed Name: %r", name_attr
        )
        return None

    # Schema relationship (required)
    schema_refs = get_relationship_references(element, "Schema")
    if not schema_refs:
        logger.warning(
            "SqlView %r has no Schema relationship — skipping", name_attr
        )
        return None
    schema_ref = schema_refs[0]

    # QueryScript CDATA property
    cdata_result = get_cdata_property(element, "QueryScript")
    query_script = cdata_result.text if cdata_result is not None else ""

    # Columns from inline elements (SqlComputedColumn)
    column_elements = get_relationship_inline_elements(element, "Columns")
    columns = extract_columns(column_elements)

    return View(
        name=parsed_name,
        schema_ref=schema_ref,
        columns=columns,
        query_script=query_script,
    )
