"""Extractor for SqlPartitionFunction elements.

Parses partition function name, range type, parameter type, and
boundary values from each ``SqlPartitionFunction`` element in model.xml.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from constants import DAC_NAMESPACE
from interfaces.protocols import ElementExtractor
from models.domain import PartitionFunction, TypeSpecifier
from models.enums import PartitionRange
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    extract_type_specifier,
    get_relationship_inline_elements,
    get_simple_property,
)

logger = logging.getLogger(__name__)

_NS = f"{{{DAC_NAMESPACE}}}"


class SqlPartitionFunctionExtractor(ElementExtractor):
    """Extract ``PartitionFunction`` domain models from ``SqlPartitionFunction`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlPartitionFunction"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[PartitionFunction, ...]:
        """Extract partition functions with range type, parameter type, and boundary values."""
        results: list[PartitionFunction] = []
        for element in elements:
            name_attr = element.get("Name")
            if name_attr is None:
                logger.warning(
                    "Skipping SqlPartitionFunction element with no Name attribute"
                )
                continue

            try:
                parsed_name = parse_name(name_attr)
            except ValueError:
                logger.warning(
                    "Skipping SqlPartitionFunction with malformed Name: %r", name_attr
                )
                continue

            # Range property → PartitionRange enum
            range_type = _parse_range_type(element)

            # ParameterType relationship → TypeSpecifier
            param_type = _extract_parameter_type(element)
            if param_type is None:
                logger.warning(
                    "Skipping SqlPartitionFunction %r: no ParameterType found",
                    name_attr,
                )
                continue

            # BoundaryValues relationship → ordered boundary expressions
            boundary_values = _extract_boundary_values(element)

            results.append(
                PartitionFunction(
                    name=parsed_name,
                    parameter_type=param_type,
                    range_type=range_type,
                    boundary_values=boundary_values,
                )
            )
        return tuple(results)


def _parse_range_type(element: Element) -> PartitionRange:
    """Parse the Range property into a PartitionRange enum value.

    Defaults to LEFT if absent or malformed.
    """
    raw = get_simple_property(element, "Range")
    if raw is None:
        return PartitionRange.LEFT
    try:
        return PartitionRange(int(raw))
    except (ValueError, KeyError):
        logger.warning(
            "Malformed Range value %r in SqlPartitionFunction — defaulting to LEFT",
            raw,
        )
        return PartitionRange.LEFT


def _extract_parameter_type(element: Element) -> TypeSpecifier | None:
    """Extract TypeSpecifier from the ParameterType relationship.

    The ParameterType relationship contains an inline element with
    a TypeSpecifier sub-relationship.
    """
    inline_elements = get_relationship_inline_elements(element, "ParameterType")
    if inline_elements:
        return extract_type_specifier(inline_elements[0], relationship_name="Type")
    return None


def _extract_boundary_values(element: Element) -> tuple[str, ...]:
    """Extract boundary value expressions from BoundaryValues relationship.

    Each inline ``SqlPartitionValue`` child has an ``ExpressionScript``
    property with CDATA content.  Values are collected in document order.
    """
    property_tag = f"{_NS}Property"
    value_tag = f"{_NS}Value"

    inline_elements = get_relationship_inline_elements(element, "BoundaryValues")
    values: list[str] = []
    for child in inline_elements:
        for prop in child.findall(property_tag):
            if prop.get("Name") == "ExpressionScript":
                value_elem = prop.find(value_tag)
                if value_elem is not None:
                    values.append(value_elem.text or "")
                else:
                    val = prop.get("Value")
                    if val is not None:
                        values.append(val)
    return tuple(values)
