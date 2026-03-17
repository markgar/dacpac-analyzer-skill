"""Tests for SqlPartitionSchemeExtractor — Spec 05, AC 6."""

from __future__ import annotations

import logging

import pytest

from constants import DAC_NAMESPACE
from parsing.extractors.partition_scheme import (
    SqlPartitionSchemeExtractor,
)
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


def _make_filegroup_specifier(fg_name: str) -> str:
    """Build a SqlFilegroupSpecifier inline element."""
    return (
        f'<Element Type="SqlFilegroupSpecifier">'
        f'<Relationship Name="Filegroup">'
        f"<Entry>"
        f'<References Name="{fg_name}" />'
        f"</Entry>"
        f"</Relationship>"
        f"</Element>"
    )


def _make_partition_scheme(
    name: str,
    *,
    partition_function: str = "[PF_Default]",
    filegroup_names: tuple[str, ...] = (),
) -> str:
    """Build a SqlPartitionScheme element XML string."""
    fg_entries = "".join(
        f"<Entry>{_make_filegroup_specifier(fg)}</Entry>"
        for fg in filegroup_names
    )
    fg_rel = ""
    if filegroup_names:
        fg_rel = (
            f'<Relationship Name="FilegroupSpecifiers">'
            f"{fg_entries}"
            f"</Relationship>"
        )

    return (
        f'<Element Type="SqlPartitionScheme" Name="{name}">'
        f'<Relationship Name="PartitionFunction">'
        f"<Entry>"
        f'<References Name="{partition_function}" />'
        f"</Entry>"
        f"</Relationship>"
        f"{fg_rel}"
        f"</Element>"
    )


class TestAC6PartitionSchemeExtraction:
    """AC 6: GIVEN a SqlPartitionScheme referencing [PF_OrderDate] with two filegroups
    WHEN extracted THEN partition_function.parts is ['PF_OrderDate'] and filegroups has two entries in order."""

    def test_function_ref_and_filegroups(self) -> None:
        elements_xml = _make_partition_scheme(
            "[PS_OrderDate]",
            partition_function="[PF_OrderDate]",
            filegroup_names=("[FG1]", "[FG2]"),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionSchemeExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.partition_schemes) == 1
        ps = model.partition_schemes[0]
        assert ps.name.parts == ("PS_OrderDate",)
        assert ps.partition_function.parts == ("PF_OrderDate",)
        assert len(ps.filegroups) == 2
        assert ps.filegroups[0].parts == ("FG1",)
        assert ps.filegroups[1].parts == ("FG2",)

    def test_filegroups_order_preserved(self) -> None:
        """Filegroups must be in document order."""
        elements_xml = _make_partition_scheme(
            "[PS_Test]",
            partition_function="[PF_Test]",
            filegroup_names=("[FG_C]", "[FG_A]", "[FG_B]"),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionSchemeExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        ps = model.partition_schemes[0]
        assert tuple(fg.parts for fg in ps.filegroups) == (
            ("FG_C",),
            ("FG_A",),
            ("FG_B",),
        )


class TestNoFilegroups:
    """Edge case: No filegroups → empty tuple."""

    def test_empty_filegroups(self) -> None:
        elements_xml = _make_partition_scheme(
            "[PS_Empty]",
            partition_function="[PF_Test]",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionSchemeExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.partition_schemes) == 1
        assert model.partition_schemes[0].filegroups == ()


class TestExtractorElementType:
    """Verify extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlPartitionSchemeExtractor()
        assert extractor.element_type == "SqlPartitionScheme"


class TestMissingNameSkipped:
    """Edge case: Element with no Name attribute is skipped with warning."""

    def test_missing_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlPartitionScheme">'
            '<Relationship Name="PartitionFunction">'
            "<Entry>"
            '<References Name="[PF_Test]" />'
            "</Entry>"
            "</Relationship>"
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionSchemeExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(
            logging.WARNING,
            logger="parsing.extractors.partition_scheme",
        ):
            model = parser.parse(content).database_model

        assert len(model.partition_schemes) == 0
        assert any("no Name" in msg for msg in caplog.messages)


class TestMissingPartitionFunctionSkipped:
    """Edge case: Missing PartitionFunction relationship skips the element."""

    def test_missing_func_ref(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlPartitionScheme" Name="[PS_NoFunc]">'
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionSchemeExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(
            logging.WARNING,
            logger="parsing.extractors.partition_scheme",
        ):
            model = parser.parse(content).database_model

        assert len(model.partition_schemes) == 0
        assert any("PartitionFunction" in msg for msg in caplog.messages)


class TestMultiplePartitionSchemes:
    """Multiple partition schemes are all extracted."""

    def test_multiple(self) -> None:
        elements_xml = (
            _make_partition_scheme(
                "[PS_Date]",
                partition_function="[PF_Date]",
                filegroup_names=("[FG1]",),
            )
            + _make_partition_scheme(
                "[PS_Int]",
                partition_function="[PF_Int]",
                filegroup_names=("[FG2]", "[FG3]"),
            )
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionSchemeExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.partition_schemes) == 2
        assert model.partition_schemes[0].name.parts == ("PS_Date",)
        assert model.partition_schemes[1].name.parts == ("PS_Int",)
        assert len(model.partition_schemes[1].filegroups) == 2
