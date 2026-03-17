"""Tests for element scanning and parsing context (Spec 04 §2–§3).

Covers acceptance criteria AC2, AC3 and edge cases.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import pytest

from constants import DAC_NAMESPACE
from models.enums import ElementType
from parsing.context import ParsingContext, scan_elements

NS = DAC_NAMESPACE


def _model_xml(*elements: str) -> ET.Element:
    """Build a <Model> element containing the given <Element> XML strings."""
    xml = (
        f'<Model xmlns="{NS}">'
        + "".join(elements)
        + "</Model>"
    )
    return ET.fromstring(xml)


def _element(type_str: str, name: str | None = None) -> str:
    """Build an <Element Type="..." Name="..."> XML string."""
    parts = [f'<Element Type="{type_str}"']
    if name is not None:
        parts.append(f' Name="{name}"')
    parts.append(" />")
    return "".join(parts)


class TestElementScanningAC2:
    """AC2: 5 SqlTable + 3 SqlSchema → correct groups."""

    def test_groups_by_type(self) -> None:
        elements = [_element("SqlTable", f"[dbo].[T{i}]") for i in range(5)]
        elements += [_element("SqlSchema", f"[S{i}]") for i in range(3)]
        model = _model_xml(*elements)
        ctx = scan_elements(model)

        groups = ctx.element_groups
        assert len(groups[ElementType.TABLE]) == 5
        assert len(groups[ElementType.SCHEMA]) == 3

    def test_total_element_count(self) -> None:
        elements = [
            _element("SqlTable", "[dbo].[T1]"),
            _element("SqlView", "[dbo].[V1]"),
            _element("SqlProcedure", "[dbo].[P1]"),
        ]
        model = _model_xml(*elements)
        ctx = scan_elements(model)

        groups = ctx.element_groups
        assert len(groups[ElementType.TABLE]) == 1
        assert len(groups[ElementType.VIEW]) == 1
        assert len(groups[ElementType.PROCEDURE]) == 1


class TestNameIndexAC3:
    """AC3: name lookup returns correct element for [Application].[Countries]."""

    def test_lookup_by_name(self) -> None:
        model = _model_xml(
            _element("SqlTable", "[Application].[Countries]"),
            _element("SqlTable", "[dbo].[Users]"),
        )
        ctx = scan_elements(model)

        result = ctx.lookup_name("[Application].[Countries]")
        assert result is not None
        assert result.get("Name") == "[Application].[Countries]"
        assert result.get("Type") == "SqlTable"

    def test_lookup_missing_returns_none(self) -> None:
        model = _model_xml(_element("SqlTable", "[dbo].[T1]"))
        ctx = scan_elements(model)
        assert ctx.lookup_name("[nonexistent]") is None

    def test_name_index_dict(self) -> None:
        model = _model_xml(
            _element("SqlTable", "[dbo].[A]"),
            _element("SqlSchema", "[dbo]"),
        )
        ctx = scan_elements(model)

        index = ctx.name_index
        assert "[dbo].[A]" in index
        assert "[dbo]" in index
        assert len(index) == 2


class TestElementWithoutName:
    """Elements without a Name attribute are grouped but not indexed."""

    def test_no_name_grouped_but_not_indexed(self) -> None:
        model = _model_xml(_element("SqlDatabaseOptions"))
        ctx = scan_elements(model)

        groups = ctx.element_groups
        assert ElementType.DATABASE_OPTIONS in groups
        assert len(groups[ElementType.DATABASE_OPTIONS]) == 1
        assert len(ctx.name_index) == 0


class TestUnknownTypeMapping:
    """Unknown types map to UNKNOWN and log a warning."""

    def test_unknown_type_mapped(self) -> None:
        model = _model_xml(_element("UnrecognizedFutureType", "[dbo].[X]"))
        ctx = scan_elements(model)

        groups = ctx.element_groups
        assert ElementType.UNKNOWN in groups
        assert len(groups[ElementType.UNKNOWN]) == 1

    def test_unknown_type_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        model = _model_xml(_element("UnrecognizedFutureType", "[dbo].[X]"))
        with caplog.at_level(logging.WARNING):
            scan_elements(model)

        assert "UnrecognizedFutureType" in caplog.text
        assert "UNKNOWN" in caplog.text

    def test_multiple_unknown_types_counted(self, caplog: pytest.LogCaptureFixture) -> None:
        model = _model_xml(
            _element("FutureType1", "[dbo].[A]"),
            _element("FutureType1", "[dbo].[B]"),
            _element("FutureType2", "[dbo].[C]"),
        )
        with caplog.at_level(logging.WARNING):
            scan_elements(model)

        assert "FutureType1" in caplog.text
        assert "2 time(s)" in caplog.text
        assert "FutureType2" in caplog.text
        assert "1 time(s)" in caplog.text


class TestEmptyModel:
    """Empty <Model> with no elements."""

    def test_empty_groups(self) -> None:
        model = _model_xml()
        ctx = scan_elements(model)

        assert ctx.element_groups == {}
        assert ctx.name_index == {}

    def test_namespace_set(self) -> None:
        model = _model_xml()
        ctx = scan_elements(model)
        assert ctx.namespace == DAC_NAMESPACE


class TestParsingContextImmutability:
    """ParsingContext is frozen."""

    def test_frozen(self) -> None:
        ctx = ParsingContext(
            _element_groups=(),
            _name_index=(),
            namespace=DAC_NAMESPACE,
        )
        with pytest.raises(AttributeError):
            ctx.namespace = "changed"  # type: ignore[misc]


class TestParsingContextParseName:
    """ParsingContext exposes the canonical name parser."""

    def test_parse_name(self) -> None:
        ctx = ParsingContext(
            _element_groups=(),
            _name_index=(),
            namespace=DAC_NAMESPACE,
        )
        parsed = ctx.parse_name("[dbo].[MyTable]")
        assert parsed.schema_name == "dbo"
        assert parsed.object_name == "MyTable"


class TestElementWithNoTypeAttribute:
    """Elements missing the Type attribute are skipped with a warning."""

    def test_no_type_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        xml = f'<Model xmlns="{NS}"><Element Name="[dbo].[X]" /></Model>'
        model = ET.fromstring(xml)
        with caplog.at_level(logging.WARNING):
            ctx = scan_elements(model)

        assert len(ctx.element_groups) == 0
        assert "no Type" in caplog.text


class TestNonElementChildrenIgnored:
    """Non-Element children of <Model> are silently ignored."""

    def test_non_element_children(self) -> None:
        xml = (
            f'<Model xmlns="{NS}">'
            '<SomethingElse Name="ignored" />'
            '<Element Type="SqlTable" Name="[dbo].[T]" />'
            "</Model>"
        )
        model = ET.fromstring(xml)
        ctx = scan_elements(model)

        groups = ctx.element_groups
        assert len(groups) == 1
        assert ElementType.TABLE in groups
