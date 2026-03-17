"""Extractor for SqlScalarFunction elements.

Produces fully populated ``ScalarFunction`` domain models from
``SqlScalarFunction`` elements in model.xml, including parameter
extraction, return type extraction, and nested function body
navigation.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import ScalarFunction
from parsing.extractors.column_helpers import (
    extract_function_body,
    extract_parameters,
)
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    extract_type_specifier,
    get_relationship_references,
)

logger = logging.getLogger(__name__)


class SqlScalarFunctionExtractor(ElementExtractor):
    """Extract ``ScalarFunction`` domain models from ``SqlScalarFunction`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlScalarFunction"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[ScalarFunction, ...]:
        """Extract scalar functions with parameters, return type, and body."""
        results: list[ScalarFunction] = []
        for element in elements:
            func = _extract_single_scalar_function(element)
            if func is not None:
                results.append(func)
        return tuple(results)


def _extract_single_scalar_function(element: Element) -> ScalarFunction | None:
    """Extract a single ``ScalarFunction`` from a ``SqlScalarFunction`` element.

    Returns ``None`` if the element has no valid Name, Schema, or return type.
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlScalarFunction with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlScalarFunction with malformed Name: %r", name_attr
        )
        return None

    schema_refs = get_relationship_references(element, "Schema")
    if not schema_refs:
        logger.warning(
            "SqlScalarFunction %r has no Schema relationship — skipping",
            name_attr,
        )
        return None
    schema_ref = schema_refs[0]

    # Return type from the "Type" relationship (same structure as TypeSpecifier)
    return_type = extract_type_specifier(element, relationship_name="Type")
    if return_type is None:
        logger.warning(
            "SqlScalarFunction %r has no return type — skipping", name_attr
        )
        return None

    parameters = extract_parameters(element)

    body_script, body_dependencies = extract_function_body(element)

    return ScalarFunction(
        name=parsed_name,
        schema_ref=schema_ref,
        return_type=return_type,
        parameters=parameters,
        body_script=body_script,
        body_dependencies=body_dependencies,
    )
