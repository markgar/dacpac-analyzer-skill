"""Registry for element-type extractors.

Implements the Open/Closed Principle: new element extractors are
registered without modifying existing parsing code. The registry
dispatches element groups to matching extractors and collects results.
"""

from __future__ import annotations

import logging
from typing import Any

from interfaces.protocols import ElementExtractor
from models.enums import ElementType
from parsing.context import ParsingContext

logger = logging.getLogger(__name__)


class ExtractorRegistry:
    """Registry mapping element types to their extractors.

    Each extractor declares which ``Type`` value it handles via its
    ``element_type`` property. Registration is explicit; duplicate
    registrations raise ``ValueError``.
    """

    def __init__(self) -> None:
        self._extractors: dict[str, ElementExtractor] = {}

    def register(self, extractor: ElementExtractor) -> None:
        """Register an extractor for its declared element type.

        Raises ``ValueError`` if an extractor is already registered
        for the same type string.
        """
        type_key = extractor.element_type
        if type_key in self._extractors:
            raise ValueError(
                f"Duplicate extractor registration for type {type_key!r}: "
                f"already registered {self._extractors[type_key]!r}"
            )
        self._extractors[type_key] = extractor

    def get(self, element_type: str) -> ElementExtractor | None:
        """Return the extractor for a given type string, or ``None``."""
        return self._extractors.get(element_type)

    @property
    def registered_types(self) -> tuple[str, ...]:
        """Return all registered type strings as an immutable tuple."""
        return tuple(self._extractors.keys())

    def __len__(self) -> int:
        return len(self._extractors)

    def __contains__(self, element_type: str) -> bool:
        return element_type in self._extractors

    def dispatch(
        self, context: ParsingContext
    ) -> dict[str, tuple[Any, ...]]:
        """Dispatch element groups to registered extractors.

        Iterates over all element groups in the context. For each group
        with a matching extractor, invokes ``extractor.extract()`` and
        collects results. Groups with no registered extractor are logged
        and skipped.

        Returns a dict mapping element type strings to extractor results.
        """
        results: dict[str, tuple[Any, ...]] = {}

        for element_type, elements in context.element_groups.items():
            if element_type is ElementType.UNKNOWN:
                continue

            type_str = element_type.value
            extractor = self._extractors.get(type_str)

            if extractor is None:
                logger.debug(
                    "No extractor registered for type %r — skipping %d element(s)",
                    type_str,
                    len(elements),
                )
                continue

            extracted = extractor.extract(elements, context)
            results[type_str] = extracted

        return results
