"""Extractors for index element types.

Covers SqlIndex and SqlColumnStoreIndex. Both produce ``Index``
domain models from model.xml elements.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import Index
from parsing.extractors.column_helpers import extract_indexed_columns
from parsing.name_parser import parse_name
from parsing.xml_helpers import get_relationship_references

logger = logging.getLogger(__name__)


class SqlIndexExtractor(ElementExtractor):
    """Extract ``Index`` domain models from ``SqlIndex`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlIndex"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Index, ...]:
        results: list[Index] = []
        for element in elements:
            idx = _extract_index(element, is_columnstore=False)
            if idx is not None:
                results.append(idx)
        return tuple(results)


class SqlColumnStoreIndexExtractor(ElementExtractor):
    """Extract ``Index`` domain models from ``SqlColumnStoreIndex`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlColumnStoreIndex"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Index, ...]:
        results: list[Index] = []
        for element in elements:
            idx = _extract_index(element, is_columnstore=True)
            if idx is not None:
                results.append(idx)
        return tuple(results)


def _extract_index(element: Element, *, is_columnstore: bool) -> Index | None:
    """Extract a single ``Index`` from a SqlIndex or SqlColumnStoreIndex element."""
    type_label = "SqlColumnStoreIndex" if is_columnstore else "SqlIndex"

    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping %s element with no Name attribute", type_label)
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping %s with malformed Name: %r", type_label, name_attr
        )
        return None

    indexed_obj_refs = get_relationship_references(element, "IndexedObject")
    if not indexed_obj_refs:
        logger.warning(
            "%s %r has no IndexedObject — skipping", type_label, name_attr
        )
        return None
    indexed_object = indexed_obj_refs[0]

    columns = extract_indexed_columns(element)

    fg_refs = get_relationship_references(element, "Filegroup")
    filegroup = fg_refs[0] if fg_refs else None

    return Index(
        name=parsed_name,
        indexed_object=indexed_object,
        columns=columns,
        filegroup=filegroup,
        is_columnstore=is_columnstore,
    )
