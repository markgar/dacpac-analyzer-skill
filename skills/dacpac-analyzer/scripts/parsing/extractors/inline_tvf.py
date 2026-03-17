"""Extractor for SqlInlineTableValuedFunction elements.

Produces fully populated ``InlineTableValuedFunction`` domain models from
``SqlInlineTableValuedFunction`` elements in model.xml, including parameter
extraction, output column extraction, and nested function body navigation.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import InlineTableValuedFunction
from parsing.extractors.column_helpers import (
    extract_columns,
    extract_function_body,
    extract_parameters,
)
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    get_relationship_inline_elements,
    get_relationship_references,
)

logger = logging.getLogger(__name__)


class SqlInlineTableValuedFunctionExtractor(ElementExtractor):
    """Extract ``InlineTableValuedFunction`` models from ``SqlInlineTableValuedFunction`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlInlineTableValuedFunction"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[InlineTableValuedFunction, ...]:
        """Extract inline table-valued functions with parameters, columns, and body."""
        results: list[InlineTableValuedFunction] = []
        for element in elements:
            func = _extract_single_inline_tvf(element)
            if func is not None:
                results.append(func)
        return tuple(results)


def _extract_single_inline_tvf(
    element: Element,
) -> InlineTableValuedFunction | None:
    """Extract a single ``InlineTableValuedFunction`` from a ``SqlInlineTableValuedFunction`` element.

    Returns ``None`` if the element has no valid Name or Schema relationship.
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning(
            "Skipping SqlInlineTableValuedFunction with no Name attribute"
        )
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlInlineTableValuedFunction with malformed Name: %r",
            name_attr,
        )
        return None

    schema_refs = get_relationship_references(element, "Schema")
    if not schema_refs:
        logger.warning(
            "SqlInlineTableValuedFunction %r has no Schema relationship — skipping",
            name_attr,
        )
        return None
    schema_ref = schema_refs[0]

    parameters = extract_parameters(element)

    column_elements = get_relationship_inline_elements(element, "Columns")
    columns = extract_columns(column_elements)

    body_script, body_dependencies = extract_function_body(element)

    return InlineTableValuedFunction(
        name=parsed_name,
        schema_ref=schema_ref,
        parameters=parameters,
        columns=columns,
        body_script=body_script,
        body_dependencies=body_dependencies,
    )
