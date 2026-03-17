"""Extractor for SqlFilegroup elements.

Parses filegroup name and the optional ``ContainsMemoryOptimizedData``
property from each ``SqlFilegroup`` element in model.xml.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import Filegroup
from parsing.name_parser import parse_name
from parsing.xml_helpers import get_simple_property

logger = logging.getLogger(__name__)


class SqlFilegroupExtractor(ElementExtractor):
    """Extract ``Filegroup`` domain models from ``SqlFilegroup`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlFilegroup"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Filegroup, ...]:
        """Extract filegroups with name and memory-optimized flag."""
        results: list[Filegroup] = []
        for element in elements:
            name_attr = element.get("Name")
            if name_attr is None:
                logger.warning("Skipping SqlFilegroup element with no Name attribute")
                continue

            try:
                parsed_name = parse_name(name_attr)
            except ValueError:
                logger.warning(
                    "Skipping SqlFilegroup with malformed Name: %r", name_attr
                )
                continue

            raw_value = get_simple_property(element, "ContainsMemoryOptimizedData")
            contains_memory_optimized = (
                raw_value is not None and raw_value.lower() == "true"
            )

            results.append(
                Filegroup(
                    name=parsed_name,
                    contains_memory_optimized_data=contains_memory_optimized,
                )
            )
        return tuple(results)
