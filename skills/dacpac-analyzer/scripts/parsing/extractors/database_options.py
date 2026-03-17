"""Extractor for SqlDatabaseOptions elements.

There is exactly one ``SqlDatabaseOptions`` element per model.  It
contains numerous ``<Property>`` children representing database-level
settings.  All property names and values are stored as strings — no
interpretation is performed at this layer.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from constants import DAC_NAMESPACE
from interfaces.protocols import ElementExtractor
from models.domain import DatabaseOptions

logger = logging.getLogger(__name__)

_NS = f"{{{DAC_NAMESPACE}}}"


class SqlDatabaseOptionsExtractor(ElementExtractor):
    """Extract ``DatabaseOptions`` from ``SqlDatabaseOptions`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlDatabaseOptions"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[DatabaseOptions, ...]:
        """Extract database options from each element.

        Only ``<Property>`` children are collected; ``<Annotation>``
        children and ``Disambiguator`` attributes are ignored.
        """
        results: list[DatabaseOptions] = []
        for element in elements:
            props = _collect_properties(element)
            results.append(DatabaseOptions(_properties=props))
        return tuple(results)


def _collect_properties(element: Element) -> tuple[tuple[str, str], ...]:
    """Collect all ``<Property>`` children as name-value pairs.

    Each property may carry its value as a ``Value`` attribute or as
    CDATA text inside a ``<Value>`` child element.  Non-``<Property>``
    children (e.g. ``<Annotation>``) are silently skipped.
    """
    property_tag = f"{_NS}Property"
    value_tag = f"{_NS}Value"
    props: list[tuple[str, str]] = []

    for child in element.findall(property_tag):
        name = child.get("Name")
        if name is None:
            logger.warning(
                "Skipping <Property> with no Name attribute in SqlDatabaseOptions"
            )
            continue

        # Value can be an attribute or CDATA in a <Value> child
        value = child.get("Value")
        if value is None:
            value_elem = child.find(value_tag)
            if value_elem is not None:
                value = value_elem.text or ""
            else:
                value = ""

        props.append((name, value))

    return tuple(props)
