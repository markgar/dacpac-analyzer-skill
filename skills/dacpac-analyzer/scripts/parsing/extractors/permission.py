"""Extractor for SqlPermissionStatement elements.

Parses permission code, grantee, and secured object from each
``SqlPermissionStatement`` element in model.xml.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import Permission
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    get_relationship_references,
    get_simple_property,
)

logger = logging.getLogger(__name__)


class SqlPermissionStatementExtractor(ElementExtractor):
    """Extract ``Permission`` domain models from ``SqlPermissionStatement`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlPermissionStatement"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Permission, ...]:
        """Extract permission statements from elements."""
        results: list[Permission] = []
        for element in elements:
            permission = _extract_single_permission(element)
            if permission is not None:
                results.append(permission)
        return tuple(results)


def _extract_single_permission(element: Element) -> Permission | None:
    """Extract a single Permission from an XML element.

    Returns None if required fields are missing.
    """
    # Permission code is required
    permission_code = get_simple_property(element, "Permission")
    if permission_code is None:
        logger.warning(
            "Skipping SqlPermissionStatement with no Permission property"
        )
        return None

    # Grantee is required
    grantee_refs = get_relationship_references(element, "Grantee")
    if not grantee_refs:
        logger.warning(
            "Skipping SqlPermissionStatement with no Grantee relationship"
        )
        return None

    # Name is optional for permission statements
    name_attr = element.get("Name")
    parsed_name = None
    if name_attr is not None:
        try:
            parsed_name = parse_name(name_attr)
        except ValueError:
            logger.warning(
                "SqlPermissionStatement has malformed Name: %r — using None",
                name_attr,
            )

    # SecuredObject is optional (absent means database-level permission)
    secured_object_refs = get_relationship_references(element, "SecuredObject")
    secured_object = secured_object_refs[0] if secured_object_refs else None

    return Permission(
        permission_code=permission_code,
        grantee=grantee_refs[0],
        name=parsed_name,
        secured_object=secured_object,
    )
