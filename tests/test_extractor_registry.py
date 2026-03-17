"""Tests for ExtractorRegistry — element-type dispatch and registration."""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

import pytest

from constants import DAC_NAMESPACE
from interfaces.protocols import ElementExtractor
from models.enums import ElementType
from parsing.context import ParsingContext
from parsing.registry import ExtractorRegistry

_NS = f"{{{DAC_NAMESPACE}}}"


class _StubExtractor(ElementExtractor):
    """Minimal concrete extractor for testing."""

    def __init__(self, type_str: str) -> None:
        self._type_str = type_str
        self.call_count = 0
        self.last_elements: Sequence[Element] = ()

    @property
    def element_type(self) -> str:
        return self._type_str

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Any, ...]:
        self.call_count += 1
        self.last_elements = elements
        return tuple(f"extracted-{i}" for i in range(len(elements)))


def _make_context(
    groups: dict[ElementType, tuple[Element, ...]],
) -> ParsingContext:
    """Build a ParsingContext from a dict of groups."""
    frozen_groups = tuple(groups.items())
    return ParsingContext(
        _element_groups=frozen_groups,
        _name_index=(),
        namespace=DAC_NAMESPACE,
    )


class TestRegisterAndRetrieve:
    """Register + retrieve round-trip."""

    def test_register_and_get_returns_extractor(self) -> None:
        registry = ExtractorRegistry()
        extractor = _StubExtractor("SqlTable")
        registry.register(extractor)

        result = registry.get("SqlTable")
        assert result is extractor

    def test_get_unregistered_returns_none(self) -> None:
        registry = ExtractorRegistry()
        assert registry.get("SqlTable") is None

    def test_registered_types_returns_all(self) -> None:
        registry = ExtractorRegistry()
        registry.register(_StubExtractor("SqlTable"))
        registry.register(_StubExtractor("SqlSchema"))

        types = registry.registered_types
        assert set(types) == {"SqlTable", "SqlSchema"}

    def test_len_and_contains(self) -> None:
        registry = ExtractorRegistry()
        assert len(registry) == 0
        assert "SqlTable" not in registry

        registry.register(_StubExtractor("SqlTable"))
        assert len(registry) == 1
        assert "SqlTable" in registry


class TestDuplicateRegistration:
    """Duplicate registration raises error."""

    def test_duplicate_raises_value_error(self) -> None:
        registry = ExtractorRegistry()
        registry.register(_StubExtractor("SqlTable"))

        with pytest.raises(ValueError, match="Duplicate extractor registration"):
            registry.register(_StubExtractor("SqlTable"))


class TestDispatch:
    """Dispatch invokes matching extractors and skips unregistered types."""

    def test_dispatches_to_registered_extractor(self) -> None:
        registry = ExtractorRegistry()
        extractor = _StubExtractor("SqlTable")
        registry.register(extractor)

        elem = Element(f"{_NS}Element", attrib={"Type": "SqlTable", "Name": "[dbo].[T1]"})
        context = _make_context({
            ElementType.TABLE: (elem,),
        })

        results = registry.dispatch(context)
        assert "SqlTable" in results
        assert results["SqlTable"] == ("extracted-0",)
        assert extractor.call_count == 1
        assert extractor.last_elements == (elem,)

    def test_dispatches_multiple_extractors(self) -> None:
        registry = ExtractorRegistry()
        table_ext = _StubExtractor("SqlTable")
        schema_ext = _StubExtractor("SqlSchema")
        registry.register(table_ext)
        registry.register(schema_ext)

        table_elem = Element(f"{_NS}Element", attrib={"Type": "SqlTable"})
        schema_elem = Element(f"{_NS}Element", attrib={"Type": "SqlSchema"})
        context = _make_context({
            ElementType.TABLE: (table_elem,),
            ElementType.SCHEMA: (schema_elem,),
        })

        results = registry.dispatch(context)
        assert len(results) == 2
        assert table_ext.call_count == 1
        assert schema_ext.call_count == 1

    def test_skips_unregistered_types_with_log(self, caplog: pytest.LogCaptureFixture) -> None:
        """Supports AC7 — unregistered types are logged and skipped."""
        registry = ExtractorRegistry()

        elem = Element(f"{_NS}Element", attrib={"Type": "SqlView"})
        context = _make_context({
            ElementType.VIEW: (elem,),
        })

        with caplog.at_level(logging.DEBUG, logger="parsing.registry"):
            results = registry.dispatch(context)

        assert len(results) == 0
        assert any("No extractor registered" in msg for msg in caplog.messages)

    def test_skips_unknown_element_type_group(self) -> None:
        """UNKNOWN groups are always skipped (already warned at scan time)."""
        registry = ExtractorRegistry()

        elem = Element(f"{_NS}Element", attrib={"Type": "FutureType"})
        context = _make_context({
            ElementType.UNKNOWN: (elem,),
        })

        results = registry.dispatch(context)
        assert len(results) == 0

    def test_empty_context_returns_empty_results(self) -> None:
        registry = ExtractorRegistry()
        registry.register(_StubExtractor("SqlTable"))

        context = _make_context({})
        results = registry.dispatch(context)
        assert results == {}
