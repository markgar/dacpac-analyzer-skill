"""Element scanner and read-only parsing context for model.xml.

The scanner performs a single pass over ``<Model>`` children, grouping
elements by ``ElementType`` and building a name→element lookup index.
The ``ParsingContext`` is an immutable object passed to all
``ElementExtractor`` implementations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from constants import DAC_NAMESPACE
from models.enums import ElementType
from models.parsed_name import ParsedName
from parsing.name_parser import parse_name

logger = logging.getLogger(__name__)

_NS = f"{{{DAC_NAMESPACE}}}"


@dataclass(frozen=True, slots=True)
class ParsingContext:
    """Immutable context passed to element extractors during parsing.

    Provides name lookup, name parsing, namespace access, and grouped
    elements by type. Read-only from the extractor's perspective.
    """

    _element_groups: tuple[tuple[ElementType, tuple[Element, ...]], ...]
    _name_index: tuple[tuple[str, Element], ...]
    namespace: str

    @property
    def element_groups(self) -> dict[ElementType, tuple[Element, ...]]:
        """Return element groups as a dict (read-only view)."""
        return dict(self._element_groups)

    @property
    def name_index(self) -> dict[str, Element]:
        """Return name index as a dict (read-only view)."""
        return dict(self._name_index)

    def lookup_name(self, name: str) -> Element | None:
        """Look up an XML element by its bracket-quoted name string.

        Returns ``None`` if the name is not found (e.g. external/built-in).
        """
        for key, elem in self._name_index:
            if key == name:
                return elem
        return None

    @staticmethod
    def parse_name(raw: str) -> ParsedName:
        """Parse a bracket-quoted name using the canonical name parser."""
        return parse_name(raw)


def scan_elements(model_element: Element) -> ParsingContext:
    """Scan all direct ``<Element>`` children of a ``<Model>`` node.

    Performs a single pass to:
    1. Group elements by their ``ElementType`` (resolved via ``from_type_string``).
    2. Build a name index mapping ``Name`` attribute → XML element.
    3. Count and log warnings for unrecognized element types.

    Returns a fully constructed ``ParsingContext``.
    """
    groups: dict[ElementType, list[Element]] = {}
    name_index: dict[str, Element] = {}
    unknown_counts: dict[str, int] = {}

    element_tag = f"{_NS}Element"

    for child in model_element:
        if child.tag != element_tag:
            continue

        type_str = child.get("Type")
        if type_str is None:
            logger.warning("Skipping <Element> with no Type attribute")
            continue

        element_type = ElementType.from_type_string(type_str)

        if element_type is ElementType.UNKNOWN:
            unknown_counts[type_str] = unknown_counts.get(type_str, 0) + 1

        if element_type not in groups:
            groups[element_type] = []
        groups[element_type].append(child)

        name_attr = child.get("Name")
        if name_attr is not None:
            name_index[name_attr] = child

    # Log warnings for all unknown types
    for unknown_type, count in sorted(unknown_counts.items()):
        logger.warning(
            "Unrecognized element type %r encountered %d time(s) — mapped to UNKNOWN",
            unknown_type,
            count,
        )

    # Convert to immutable tuples
    frozen_groups = tuple(
        (et, tuple(elems)) for et, elems in groups.items()
    )
    frozen_name_index = tuple(name_index.items())

    return ParsingContext(
        _element_groups=frozen_groups,
        _name_index=frozen_name_index,
        namespace=DAC_NAMESPACE,
    )
