"""Extractor for SqlPartitionScheme elements.

Parses partition scheme name, partition function reference, and
filegroup specifiers from each ``SqlPartitionScheme`` element in model.xml.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import PartitionScheme
from models.parsed_name import ParsedName
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    get_relationship_inline_elements,
    get_relationship_references,
)

logger = logging.getLogger(__name__)


class SqlPartitionSchemeExtractor(ElementExtractor):
    """Extract ``PartitionScheme`` domain models from ``SqlPartitionScheme`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlPartitionScheme"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[PartitionScheme, ...]:
        """Extract partition schemes with function reference and filegroup list."""
        results: list[PartitionScheme] = []
        for element in elements:
            name_attr = element.get("Name")
            if name_attr is None:
                logger.warning(
                    "Skipping SqlPartitionScheme element with no Name attribute"
                )
                continue

            try:
                parsed_name = parse_name(name_attr)
            except ValueError:
                logger.warning(
                    "Skipping SqlPartitionScheme with malformed Name: %r", name_attr
                )
                continue

            # PartitionFunction relationship → References
            func_refs = get_relationship_references(element, "PartitionFunction")
            if not func_refs:
                logger.warning(
                    "Skipping SqlPartitionScheme %r: no PartitionFunction reference",
                    name_attr,
                )
                continue
            partition_function = func_refs[0]

            # FilegroupSpecifiers relationship → inline elements with Filegroup sub-refs
            filegroups = _extract_filegroup_specifiers(element)

            results.append(
                PartitionScheme(
                    name=parsed_name,
                    partition_function=partition_function,
                    filegroups=filegroups,
                )
            )
        return tuple(results)


def _extract_filegroup_specifiers(element: Element) -> tuple[ParsedName, ...]:
    """Extract filegroup references from FilegroupSpecifiers inline elements.

    Each ``SqlFilegroupSpecifier`` inline element contains a ``Filegroup``
    relationship with a ``<References>`` to a filegroup name.  Results are
    collected in document order.
    """
    inline_elements = get_relationship_inline_elements(element, "FilegroupSpecifiers")
    filegroups: list[ParsedName] = []
    for specifier in inline_elements:
        fg_refs = get_relationship_references(specifier, "Filegroup")
        if fg_refs:
            filegroups.append(fg_refs[0])
        else:
            logger.warning(
                "SqlFilegroupSpecifier has no Filegroup reference — skipping"
            )
    return tuple(filegroups)
