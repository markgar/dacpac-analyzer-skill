"""Extractor for SqlProcedure elements.

Produces fully populated ``Procedure`` domain models from ``SqlProcedure``
elements in model.xml, including parameter extraction, execute-as resolution,
and body script attribute extraction.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import Procedure
from parsing.extractors.column_helpers import extract_parameters
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    get_cdata_property,
    get_relationship_references,
    get_simple_property,
)

logger = logging.getLogger(__name__)


class SqlProcedureExtractor(ElementExtractor):
    """Extract ``Procedure`` domain models from ``SqlProcedure`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlProcedure"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Procedure, ...]:
        """Extract procedures with parameters, body script, and execution context."""
        results: list[Procedure] = []
        for element in elements:
            proc = _extract_single_procedure(element)
            if proc is not None:
                results.append(proc)
        return tuple(results)


def _extract_single_procedure(element: Element) -> Procedure | None:
    """Extract a single ``Procedure`` from a ``SqlProcedure`` element.

    Returns ``None`` if the element has no valid Name or Schema relationship.
    """
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlProcedure with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning("Skipping SqlProcedure with malformed Name: %r", name_attr)
        return None

    schema_refs = get_relationship_references(element, "Schema")
    if not schema_refs:
        logger.warning(
            "SqlProcedure %r has no Schema relationship — skipping", name_attr
        )
        return None
    schema_ref = schema_refs[0]

    parameters = extract_parameters(element)

    body_result = get_cdata_property(element, "BodyScript")
    body_script = body_result.text if body_result is not None else ""

    # is_quoted_identifiers_on from <Value> element's QuotedIdentifiers attribute
    is_quoted_identifiers_on = True
    if body_result is not None and body_result.quoted_identifiers is not None:
        is_quoted_identifiers_on = body_result.quoted_identifiers

    body_dependencies = get_relationship_references(element, "BodyDependencies")

    # IsAnsiNullsOn from simple property (defaults to True)
    ansi_nulls_val = get_simple_property(element, "IsAnsiNullsOn")
    is_ansi_nulls_on = ansi_nulls_val is None or ansi_nulls_val.lower() != "false"

    execute_as = _resolve_execute_as(element)

    return Procedure(
        name=parsed_name,
        schema_ref=schema_ref,
        parameters=parameters,
        body_script=body_script,
        body_dependencies=body_dependencies,
        is_ansi_nulls_on=is_ansi_nulls_on,
        is_quoted_identifiers_on=is_quoted_identifiers_on,
        execute_as=execute_as,
    )


def _resolve_execute_as(element: Element) -> str | None:
    """Resolve the EXECUTE AS context from IsOwner/IsCaller properties.

    | IsOwner | IsCaller | Result  |
    |---------|----------|---------|
    | True    | False    | "OWNER" |
    | False   | True     | "CALLER"|
    | False   | False    | None    |
    """
    is_owner_val = get_simple_property(element, "IsOwner")
    is_caller_val = get_simple_property(element, "IsCaller")

    is_owner = is_owner_val is not None and is_owner_val.lower() == "true"
    is_caller = is_caller_val is not None and is_caller_val.lower() == "true"

    if is_owner:
        return "OWNER"
    if is_caller:
        return "CALLER"
    return None
