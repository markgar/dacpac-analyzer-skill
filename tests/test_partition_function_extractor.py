"""Tests for SqlPartitionFunctionExtractor — Spec 05, AC 5."""

from __future__ import annotations

import logging

import pytest

from constants import DAC_NAMESPACE
from models.enums import PartitionRange
from parsing.extractors.partition_function import (
    SqlPartitionFunctionExtractor,
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


def _make_boundary_value(expression: str) -> str:
    """Build a SqlPartitionValue inline element."""
    return (
        f'<Element Type="SqlPartitionValue">'
        f'<Property Name="ExpressionScript">'
        f"<Value><![CDATA[{expression}]]></Value>"
        f"</Property>"
        f"</Element>"
    )


def _make_partition_function(
    name: str,
    *,
    range_val: str = "1",
    type_name: str = "[datetime]",
    boundary_expressions: tuple[str, ...] = (),
) -> str:
    """Build a SqlPartitionFunction element XML string."""
    boundary_entries = "".join(
        f"<Entry>{_make_boundary_value(expr)}</Entry>"
        for expr in boundary_expressions
    )
    boundary_rel = ""
    if boundary_expressions:
        boundary_rel = (
            f'<Relationship Name="BoundaryValues">'
            f"{boundary_entries}"
            f"</Relationship>"
        )

    return (
        f'<Element Type="SqlPartitionFunction" Name="{name}">'
        f'<Property Name="Range" Value="{range_val}" />'
        f'<Relationship Name="ParameterType">'
        f"<Entry>"
        f'<Element Type="SqlTypeSpecifier">'
        f'<Relationship Name="Type">'
        f"<Entry>"
        f'<References Name="{type_name}" ExternalSource="BuiltIns" />'
        f"</Entry>"
        f"</Relationship>"
        f"</Element>"
        f"</Entry>"
        f"</Relationship>"
        f"{boundary_rel}"
        f"</Element>"
    )


class TestAC5RangeRightWithBoundaryValues:
    """AC 5: GIVEN SqlPartitionFunction with Range='2' and three boundary values
    WHEN extracted THEN range_type is RIGHT and boundary_values in order."""

    def test_range_right_and_boundary_values(self) -> None:
        elements_xml = _make_partition_function(
            "[PF_OrderDate]",
            range_val="2",
            type_name="[datetime]",
            boundary_expressions=("'20130101'", "'20140101'", "'20150101'"),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionFunctionExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.partition_functions) == 1
        pf = model.partition_functions[0]
        assert pf.name.parts == ("PF_OrderDate",)
        assert pf.range_type == PartitionRange.RIGHT
        assert pf.boundary_values == ("'20130101'", "'20140101'", "'20150101'")

    def test_parameter_type_extracted(self) -> None:
        elements_xml = _make_partition_function(
            "[PF_OrderDate]",
            range_val="2",
            type_name="[datetime]",
            boundary_expressions=("'20130101'",),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionFunctionExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        pf = model.partition_functions[0]
        assert pf.parameter_type.type_name == "datetime"
        assert pf.parameter_type.is_builtin is True


class TestRangeLeftDefault:
    """Range value '1' maps to LEFT."""

    def test_range_left(self) -> None:
        elements_xml = _make_partition_function(
            "[PF_Test]",
            range_val="1",
            boundary_expressions=("'2020-01-01'",),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionFunctionExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.partition_functions[0].range_type == PartitionRange.LEFT


class TestNoBoundaryValues:
    """Edge case: No boundary values → empty tuple."""

    def test_empty_boundary_values(self) -> None:
        elements_xml = _make_partition_function(
            "[PF_Empty]",
            range_val="1",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionFunctionExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.partition_functions) == 1
        assert model.partition_functions[0].boundary_values == ()


class TestExtractorElementType:
    """Verify extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlPartitionFunctionExtractor()
        assert extractor.element_type == "SqlPartitionFunction"


class TestMissingNameSkipped:
    """Edge case: Element with no Name attribute is skipped with warning."""

    def test_missing_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlPartitionFunction">'
            '<Property Name="Range" Value="1" />'
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionFunctionExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(
            logging.WARNING,
            logger="parsing.extractors.partition_function",
        ):
            model = parser.parse(content).database_model

        assert len(model.partition_functions) == 0
        assert any("no Name" in msg for msg in caplog.messages)


class TestMalformedRangeDefaultsToLeft:
    """Edge case: Malformed Range value defaults to LEFT with warning."""

    def test_malformed_range(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlPartitionFunction" Name="[PF_Bad]">'
            '<Property Name="Range" Value="invalid" />'
            '<Relationship Name="ParameterType">'
            "<Entry>"
            '<Element Type="SqlTypeSpecifier">'
            '<Relationship Name="Type">'
            "<Entry>"
            '<References Name="[int]" ExternalSource="BuiltIns" />'
            "</Entry>"
            "</Relationship>"
            "</Element>"
            "</Entry>"
            "</Relationship>"
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionFunctionExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(
            logging.WARNING,
            logger="parsing.extractors.partition_function",
        ):
            model = parser.parse(content).database_model

        assert len(model.partition_functions) == 1
        assert model.partition_functions[0].range_type == PartitionRange.LEFT
        assert any("malformed" in msg.lower() for msg in caplog.messages)


class TestMissingParameterTypeSkipped:
    """Edge case: Missing ParameterType relationship skips the element."""

    def test_missing_param_type(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlPartitionFunction" Name="[PF_NoType]">'
            '<Property Name="Range" Value="1" />'
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionFunctionExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(
            logging.WARNING,
            logger="parsing.extractors.partition_function",
        ):
            model = parser.parse(content).database_model

        assert len(model.partition_functions) == 0
        assert any("ParameterType" in msg for msg in caplog.messages)


class TestMultiplePartitionFunctions:
    """Multiple partition functions are all extracted."""

    def test_multiple(self) -> None:
        elements_xml = (
            _make_partition_function(
                "[PF_Date]",
                range_val="2",
                boundary_expressions=("'20200101'",),
            )
            + _make_partition_function(
                "[PF_Int]",
                range_val="1",
                type_name="[int]",
                boundary_expressions=("100", "200"),
            )
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPartitionFunctionExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.partition_functions) == 2
        assert model.partition_functions[0].name.parts == ("PF_Date",)
        assert model.partition_functions[1].name.parts == ("PF_Int",)
        assert model.partition_functions[1].boundary_values == ("100", "200")
