"""Extractor for SqlExtendedProperty elements.

Parses extended property name, host reference, and value (with
surrounding single-quote stripping) for each ``SqlExtendedProperty``
element in model.xml.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import ExtendedProperty
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    get_cdata_property,
    get_relationship_references,
)

logger = logging.getLogger(__name__)


class SqlExtendedPropertyExtractor(ElementExtractor):
    """Extract ``ExtendedProperty`` domain models from ``SqlExtendedProperty`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlExtendedProperty"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[ExtendedProperty, ...]:
        """Extract extended properties with host reference and cleaned value."""
        results: list[ExtendedProperty] = []
        for element in elements:
            ep = _extract_single_extended_property(element)
            if ep is not None:
                results.append(ep)
        return tuple(results)


def _extract_single_extended_property(
    element: Element,
) -> ExtendedProperty | None:
    """Extract a single ``ExtendedProperty`` from a ``SqlExtendedProperty`` element.

    Returns ``None`` if the element has no valid Name attribute or is
    missing the required Host relationship.
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlExtendedProperty element with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlExtendedProperty with malformed Name: %r", name_attr
        )
        return None

    # Host relationship (required)
    host_refs = get_relationship_references(element, "Host")
    if not host_refs:
        logger.warning(
            "SqlExtendedProperty %r has no Host relationship — skipping",
            name_attr,
        )
        return None
    host = host_refs[0]

    # Value CDATA property with quote stripping
    cdata_result = get_cdata_property(element, "Value")
    raw_value = cdata_result.text if cdata_result is not None else ""
    value = _strip_surrounding_quotes(raw_value)

    return ExtendedProperty(
        name=parsed_name,
        host=host,
        value=value,
    )


def _strip_surrounding_quotes(value: str) -> str:
    """Strip surrounding single quotes from a value string.

    If the value starts and ends with ``'``, those quotes are removed.
    Otherwise the value is returned as-is. Empty strings remain empty.
    """
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1]
    return value
