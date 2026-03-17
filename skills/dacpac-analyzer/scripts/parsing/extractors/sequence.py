"""Extractor for SqlSequence elements.

Parses sequence name, schema reference, numeric properties, type
specifier, and current value from ``OnlinePropertyAnnotation`` for
each ``SqlSequence`` element in model.xml.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from constants import DAC_NAMESPACE
from interfaces.protocols import ElementExtractor
from models.domain import Sequence as SequenceModel
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    extract_type_specifier,
    get_relationship_references,
    get_simple_property,
)

logger = logging.getLogger(__name__)

_NS = f"{{{DAC_NAMESPACE}}}"

_ONLINE_PROPERTY_ANNOTATION_TYPE = "OnlinePropertyAnnotation"


class SqlSequenceExtractor(ElementExtractor):
    """Extract ``Sequence`` domain models from ``SqlSequence`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlSequence"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[SequenceModel, ...]:
        """Extract sequences with properties, type specifier, and annotation current value."""
        results: list[SequenceModel] = []
        for element in elements:
            seq = _extract_single_sequence(element)
            if seq is not None:
                results.append(seq)
        return tuple(results)


def _extract_single_sequence(element: Element) -> SequenceModel | None:
    """Extract a single ``Sequence`` from a ``SqlSequence`` element.

    Returns ``None`` if the element has no valid Name attribute or is
    missing required fields (Schema, TypeSpecifier).
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlSequence element with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlSequence with malformed Name: %r", name_attr
        )
        return None

    # Schema relationship (required)
    schema_refs = get_relationship_references(element, "Schema")
    if not schema_refs:
        logger.warning(
            "SqlSequence %r has no Schema relationship — skipping", name_attr
        )
        return None
    schema_ref = schema_refs[0]

    # TypeSpecifier (required per model — Sequence.type_specifier is not optional)
    type_spec = extract_type_specifier(element)
    if type_spec is None:
        logger.warning(
            "SqlSequence %r has no TypeSpecifier — skipping", name_attr
        )
        return None

    # Increment and StartValue properties (explicit None check; do not
    # conflate absent with empty-string via `or`)
    increment_raw = get_simple_property(element, "Increment")
    increment = increment_raw if increment_raw is not None else "1"
    start_value_raw = get_simple_property(element, "StartValue")
    start_value = start_value_raw if start_value_raw is not None else "0"

    # CurrentValue from OnlinePropertyAnnotation
    current_value = _extract_current_value_from_annotation(element)

    return SequenceModel(
        name=parsed_name,
        schema_ref=schema_ref,
        type_specifier=type_spec,
        start_value=start_value,
        increment=increment,
        current_value=current_value,
    )


def _extract_current_value_from_annotation(element: Element) -> str | None:
    """Extract CurrentValue from an OnlinePropertyAnnotation child element.

    Scans direct-child ``<Annotation>`` elements (namespace-aware) for one
    with ``Type="OnlinePropertyAnnotation"``, then reads the ``CurrentValue``
    property from it.

    Returns ``None`` if no matching annotation or property is found.
    """
    for annotation in element.findall(f"{_NS}Annotation"):
        if annotation.get("Type") == _ONLINE_PROPERTY_ANNOTATION_TYPE:
            current_val = get_simple_property(annotation, "CurrentValue")
            if current_val is not None:
                return current_val
    return None
