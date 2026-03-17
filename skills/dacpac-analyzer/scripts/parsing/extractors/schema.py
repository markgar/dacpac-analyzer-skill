"""Extractor for SqlSchema elements.

Parses schema name and authorizer relationship from each
``SqlSchema`` element in model.xml.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import Schema
from parsing.name_parser import parse_name
from parsing.xml_helpers import get_relationship_references

logger = logging.getLogger(__name__)

_DEFAULT_AUTHORIZER_RAW = "[dbo]"


class SqlSchemaExtractor(ElementExtractor):
    """Extract ``Schema`` domain models from ``SqlSchema`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlSchema"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Schema, ...]:
        """Extract schemas, defaulting authorizer to ``[dbo]`` if absent."""
        results: list[Schema] = []
        for element in elements:
            name_attr = element.get("Name")
            if name_attr is None:
                logger.warning("Skipping SqlSchema element with no Name attribute")
                continue

            try:
                parsed_name = parse_name(name_attr)
            except ValueError:
                logger.warning(
                    "Skipping SqlSchema with malformed Name: %r", name_attr
                )
                continue

            authorizer_refs = get_relationship_references(
                element, "Authorizer"
            )
            if authorizer_refs:
                authorizer = authorizer_refs[0]
            else:
                authorizer = parse_name(_DEFAULT_AUTHORIZER_RAW)

            results.append(Schema(name=parsed_name, authorizer=authorizer))
        return tuple(results)
