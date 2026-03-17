"""Tests for SqlFilegroupExtractor — Spec 05, AC 3 and AC 4."""

from __future__ import annotations

import logging

import pytest

from constants import DAC_NAMESPACE
from parsing.extractors.filegroup import SqlFilegroupExtractor
from parsing.model_parser import XmlModelParser
from parsing.registry import ExtractorRegistry

_ROOT_ATTRS = (
    f'xmlns="{DAC_NAMESPACE}" '
    'FileFormatVersion="1.2" '
    'SchemaVersion="2.9" '
    'DspName="Microsoft.Data.Tools.Schema.Sql.Sql130DatabaseSchemaProvider" '
    'CollationLcid="1033" '
    'CollationCaseSensitive="False"'
)


def _make_model_xml(
    *,
    root_attrs: str = _ROOT_ATTRS,
    elements_xml: str = "",
) -> bytes:
    """Build a minimal model.xml bytes payload."""
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f"<DataSchemaModel {root_attrs}>"
        f"<Model>{elements_xml}</Model>"
        f"</DataSchemaModel>"
    ).encode("utf-8")


def _make_filegroup_element(
    name: str, *, contains_memory_optimized: str | None = None
) -> str:
    """Build a SqlFilegroup element XML string."""
    if contains_memory_optimized is not None:
        prop_xml = (
            f'<Property Name="ContainsMemoryOptimizedData" '
            f'Value="{contains_memory_optimized}" />'
        )
    else:
        prop_xml = ""
    return (
        f'<Element Type="SqlFilegroup" Name="{name}">'
        f"{prop_xml}"
        f"</Element>"
    )


class TestAC3MemoryOptimizedTrue:
    """AC 3: GIVEN SqlFilegroup with Name='[WWI_InMemory_Data]' and
    ContainsMemoryOptimizedData='True'
    WHEN extracted THEN contains_memory_optimized_data is True."""

    def test_memory_optimized_true(self) -> None:
        elements_xml = _make_filegroup_element(
            "[WWI_InMemory_Data]", contains_memory_optimized="True"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlFilegroupExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.filegroups) == 1
        fg = model.filegroups[0]
        assert fg.name.parts == ("WWI_InMemory_Data",)
        assert fg.contains_memory_optimized_data is True


class TestAC4MemoryOptimizedAbsent:
    """AC 4: GIVEN SqlFilegroup with Name='[PRIMARY]' and no
    ContainsMemoryOptimizedData property
    WHEN extracted THEN contains_memory_optimized_data is False."""

    def test_property_absent_defaults_to_false(self) -> None:
        elements_xml = _make_filegroup_element("[PRIMARY]")
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlFilegroupExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.filegroups) == 1
        fg = model.filegroups[0]
        assert fg.name.parts == ("PRIMARY",)
        assert fg.contains_memory_optimized_data is False


class TestMemoryOptimizedFalseExplicit:
    """Edge case: Explicit 'False' value for ContainsMemoryOptimizedData."""

    def test_explicit_false(self) -> None:
        elements_xml = _make_filegroup_element(
            "[USERDATA]", contains_memory_optimized="False"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlFilegroupExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.filegroups) == 1
        assert model.filegroups[0].contains_memory_optimized_data is False


class TestMultipleFilegroups:
    """Multiple filegroups are all extracted in order."""

    def test_multiple_filegroups(self) -> None:
        elements_xml = (
            _make_filegroup_element("[PRIMARY]")
            + _make_filegroup_element("[USERDATA]")
            + _make_filegroup_element(
                "[WWI_InMemory_Data]", contains_memory_optimized="True"
            )
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlFilegroupExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.filegroups) == 3
        names = [fg.name.parts[0] for fg in model.filegroups]
        assert names == ["PRIMARY", "USERDATA", "WWI_InMemory_Data"]
        assert model.filegroups[2].contains_memory_optimized_data is True


class TestExtractorElementType:
    """Verify extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlFilegroupExtractor()
        assert extractor.element_type == "SqlFilegroup"


class TestMissingNameSkipped:
    """Edge case: Element with no Name attribute is skipped with warning."""

    def test_missing_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = '<Element Type="SqlFilegroup" />'
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlFilegroupExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(
            logging.WARNING, logger="parsing.extractors.filegroup"
        ):
            model = parser.parse(content).database_model

        assert len(model.filegroups) == 0
        assert any("no Name" in msg for msg in caplog.messages)


class TestMalformedNameSkipped:
    """Edge case: Element with malformed Name is skipped with warning."""

    def test_malformed_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = '<Element Type="SqlFilegroup" Name="no_brackets" />'
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlFilegroupExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(
            logging.WARNING, logger="parsing.extractors.filegroup"
        ):
            model = parser.parse(content).database_model

        assert len(model.filegroups) == 0
        assert any("malformed" in msg.lower() for msg in caplog.messages)
