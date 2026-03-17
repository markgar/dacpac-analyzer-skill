"""Reusable XML helper functions for common model.xml patterns.

All helpers accept an ``xml.etree.ElementTree.Element`` and use
``DAC_NAMESPACE`` for namespace-qualified tag searches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from constants import BUILTIN_EXTERNAL_SOURCE, DAC_NAMESPACE
from models.domain import TypeSpecifier
from models.parsed_name import ParsedName
from parsing.name_parser import parse_name

logger = logging.getLogger(__name__)

_NS = f"{{{DAC_NAMESPACE}}}"


@dataclass(frozen=True, slots=True)
class CdataResult:
    """Result from a CDATA property extraction."""

    text: str
    quoted_identifiers: bool | None = None
    ansi_nulls: bool | None = None


def get_simple_property(element: Element, property_name: str) -> str | None:
    """Extract a simple ``<Property Name="..." Value="..." />`` value.

    Returns the ``Value`` attribute string, or ``None`` if the property
    is absent.
    """
    for prop in element.findall(f"{_NS}Property"):
        if prop.get("Name") == property_name:
            return prop.get("Value")
    return None


def get_cdata_property(element: Element, property_name: str) -> CdataResult | None:
    """Extract a CDATA property with optional Value-element attributes.

    Handles the pattern::

        <Property Name="BodyScript">
          <Value QuotedIdentifiers="True" AnsiNulls="True"><![CDATA[...]]]></Value>
        </Property>

    Returns a ``CdataResult`` with the text content and optional boolean
    attributes, or ``None`` if the property is absent.
    """
    for prop in element.findall(f"{_NS}Property"):
        if prop.get("Name") == property_name:
            value_elem = prop.find(f"{_NS}Value")
            if value_elem is not None:
                text = value_elem.text or ""
                qi = _parse_optional_bool(value_elem.get("QuotedIdentifiers"))
                an = _parse_optional_bool(value_elem.get("AnsiNulls"))
                return CdataResult(text=text, quoted_identifiers=qi, ansi_nulls=an)
            return None
    return None


def get_relationship_references(
    element: Element,
    relationship_name: str,
    *,
    exclude_builtins: bool = False,
) -> tuple[ParsedName, ...]:
    """Extract ``ParsedName`` references from a relationship.

    Handles the pattern::

        <Relationship Name="Schema">
          <Entry>
            <References Name="[dbo]" />
          </Entry>
        </Relationship>

    When *exclude_builtins* is True, entries where
    ``ExternalSource="BuiltIns"`` are skipped.
    """
    results: list[ParsedName] = []
    for rel in element.findall(f"{_NS}Relationship"):
        if rel.get("Name") == relationship_name:
            for entry in rel.findall(f"{_NS}Entry"):
                for ref in entry.findall(f"{_NS}References"):
                    if exclude_builtins and ref.get("ExternalSource") == BUILTIN_EXTERNAL_SOURCE:
                        continue
                    name_attr = ref.get("Name")
                    if name_attr is not None:
                        try:
                            results.append(parse_name(name_attr))
                        except ValueError:
                            logger.warning(
                                "Skipping malformed reference name: %r", name_attr
                            )
    return tuple(results)


def get_relationship_inline_elements(
    element: Element, relationship_name: str
) -> tuple[Element, ...]:
    """Extract inline ``<Element>`` nodes from a relationship.

    Handles the pattern::

        <Relationship Name="Columns">
          <Entry>
            <Element Type="SqlSimpleColumn" ...> ... </Element>
          </Entry>
        </Relationship>
    """
    results: list[Element] = []
    for rel in element.findall(f"{_NS}Relationship"):
        if rel.get("Name") == relationship_name:
            for entry in rel.findall(f"{_NS}Entry"):
                for child in entry:
                    tag = child.tag
                    if tag == f"{_NS}Element":
                        results.append(child)
    return tuple(results)


def extract_type_specifier(
    element: Element,
    relationship_name: str = "TypeSpecifier",
) -> TypeSpecifier | None:
    """Extract a ``TypeSpecifier`` from a named relationship.

    By default reads from the ``TypeSpecifier`` relationship.  Pass a
    different *relationship_name* (e.g. ``"Type"``) for scalar-function
    return types that use the same inner structure under a different
    relationship name.

    Returns ``None`` if no matching relationship is present.
    """
    refs = _get_type_specifier_refs(element, relationship_name)
    if not refs:
        return None

    ref_elem = refs[0]
    name_attr = ref_elem.get("Name")
    if name_attr is None:
        logger.warning("TypeSpecifier References element missing Name attribute")
        return None

    try:
        parsed = parse_name(name_attr)
    except ValueError:
        logger.warning("Malformed TypeSpecifier name: %r", name_attr)
        return None

    # The type name is the last part (e.g. [nvarchar] -> "nvarchar")
    type_name = parsed.parts[-1] if parsed.parts else name_attr

    is_builtin = ref_elem.get("ExternalSource") == BUILTIN_EXTERNAL_SOURCE

    # Extract facet properties from the Entry that contains this References
    entry_elem = _find_parent_entry(element, ref_elem, relationship_name)
    length = _get_facet_int(entry_elem, "Length")
    precision = _get_facet_int(entry_elem, "Precision")
    scale = _get_facet_int(entry_elem, "Scale")
    is_max = _get_facet_bool(entry_elem, "IsMax")

    return TypeSpecifier(
        type_name=type_name,
        is_builtin=is_builtin,
        length=length,
        precision=precision,
        scale=scale,
        is_max=is_max,
    )


def _get_type_specifier_refs(
    element: Element, relationship_name: str = "TypeSpecifier"
) -> list[Element]:
    """Find References elements inside a type-specifier-like relationship.

    Handles two patterns found in real dacpac/bacpac files:

    **Direct pattern** (rare in practice)::

        <Relationship Name="TypeSpecifier">
          <Entry>
            <References Name="[int]" />
          </Entry>
        </Relationship>

    **Inline pattern** (standard for real-world packages)::

        <Relationship Name="TypeSpecifier">
          <Entry>
            <Element Type="SqlTypeSpecifier">
              <Relationship Name="Type">
                <Entry>
                  <References Name="[int]" />
                </Entry>
              </Relationship>
            </Element>
          </Entry>
        </Relationship>
    """
    refs: list[Element] = []
    for rel in element.findall(f"{_NS}Relationship"):
        if rel.get("Name") == relationship_name:
            for entry in rel.findall(f"{_NS}Entry"):
                # Direct pattern: <Entry><References .../></Entry>
                for ref in entry.findall(f"{_NS}References"):
                    refs.append(ref)
                if refs:
                    continue
                # Inline pattern: <Entry><Element Type="SqlTypeSpecifier">
                #   <Relationship Name="Type"><Entry><References .../></Entry>
                for inline_elem in entry.findall(f"{_NS}Element"):
                    if inline_elem.get("Type") == "SqlTypeSpecifier":
                        for inner_rel in inline_elem.findall(f"{_NS}Relationship"):
                            if inner_rel.get("Name") == "Type":
                                for inner_entry in inner_rel.findall(f"{_NS}Entry"):
                                    for ref in inner_entry.findall(f"{_NS}References"):
                                        refs.append(ref)
    return refs


def _find_parent_entry(
    element: Element,
    ref_elem: Element,
    relationship_name: str = "TypeSpecifier",
) -> Element | None:
    """Walk a type-specifier-like relationship to find the container of ref_elem.

    For the **direct** pattern, returns the ``<Entry>`` holding the
    ``<References>`` (facet properties live on the Entry).

    For the **inline** pattern, returns the ``<Element Type="SqlTypeSpecifier">``
    node (facet properties live there as ``<Property>`` children).
    """
    for rel in element.findall(f"{_NS}Relationship"):
        if rel.get("Name") == relationship_name:
            for entry in rel.findall(f"{_NS}Entry"):
                # Direct pattern
                for ref in entry.findall(f"{_NS}References"):
                    if ref is ref_elem:
                        return entry
                # Inline pattern — facets are on the SqlTypeSpecifier Element
                for inline_elem in entry.findall(f"{_NS}Element"):
                    if inline_elem.get("Type") == "SqlTypeSpecifier":
                        for inner_rel in inline_elem.findall(f"{_NS}Relationship"):
                            if inner_rel.get("Name") == "Type":
                                for inner_entry in inner_rel.findall(f"{_NS}Entry"):
                                    for ref in inner_entry.findall(f"{_NS}References"):
                                        if ref is ref_elem:
                                            return inline_elem
    return None


def _get_facet_int(entry: Element | None, prop_name: str) -> int | None:
    """Extract an integer facet property from a TypeSpecifier Entry."""
    if entry is None:
        return None
    for prop in entry.findall(f"{_NS}Property"):
        if prop.get("Name") == prop_name:
            val = prop.get("Value")
            if val is not None:
                try:
                    return int(val)
                except ValueError:
                    logger.warning(
                        "Malformed integer value for %s: %r", prop_name, val
                    )
    return None


def _get_facet_bool(entry: Element | None, prop_name: str) -> bool:
    """Extract a boolean facet property from a TypeSpecifier Entry."""
    if entry is None:
        return False
    for prop in entry.findall(f"{_NS}Property"):
        if prop.get("Name") == prop_name:
            val = prop.get("Value")
            if val is not None:
                return val.lower() == "true"
    return False


def _parse_optional_bool(value: str | None) -> bool | None:
    """Parse an optional boolean attribute string."""
    if value is None:
        return None
    return value.lower() == "true"
