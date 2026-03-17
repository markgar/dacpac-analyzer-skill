"""Tests for SqlExtendedPropertyExtractor — Spec 09, AC 7 & AC 8."""

from __future__ import annotations

import logging

import pytest

from constants import DAC_NAMESPACE
from models.domain import ExtendedProperty
from parsing.extractors.extended_property import SqlExtendedPropertyExtractor
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


def _make_extended_property_element(
    name: str,
    host: str,
    *,
    value: str | None = None,
) -> str:
    """Build a SqlExtendedProperty element XML string."""
    host_rel = (
        f'<Relationship Name="Host">'
        f"<Entry>"
        f'<References Name="{host}" />'
        f"</Entry>"
        f"</Relationship>"
    )

    value_prop = ""
    if value is not None:
        value_prop = (
            f'<Property Name="Value">'
            f"<Value><![CDATA[{value}]]></Value>"
            f"</Property>"
        )

    return (
        f'<Element Type="SqlExtendedProperty" Name="{name}">'
        f"{value_prop}"
        f"{host_rel}"
        f"</Element>"
    )


class TestAC7QuotedValueStripped:
    """AC 7: GIVEN SqlExtendedProperty named
    [SqlColumn].[Application].[Cities].[CityID].[Description]
    with Host referencing [Application].[Cities].[CityID]
    and value 'Numeric ID...'
    WHEN extracted
    THEN host.parts is ['Application', 'Cities', 'CityID']
    and value is 'Numeric ID...' (quotes stripped)."""

    def test_quoted_value_stripped(self) -> None:
        elements_xml = _make_extended_property_element(
            "[SqlColumn].[Application].[Cities].[CityID].[Description]",
            "[Application].[Cities].[CityID]",
            value="'Numeric ID used for reference to a city within the database'",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlExtendedPropertyExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.extended_properties) == 1
        ep = model.extended_properties[0]
        assert ep.name.parts == (
            "SqlColumn", "Application", "Cities", "CityID", "Description",
        )
        assert ep.host.parts == ("Application", "Cities", "CityID")
        assert ep.value == "Numeric ID used for reference to a city within the database"


class TestAC8UnquotedValueAsIs:
    """AC 8: GIVEN SqlExtendedProperty with value CDATA containing no surrounding quotes
    WHEN extracted
    THEN value is the raw text as-is."""

    def test_unquoted_value_as_is(self) -> None:
        elements_xml = _make_extended_property_element(
            "[SqlTable].[dbo].[Users].[MS_Description]",
            "[dbo].[Users]",
            value="This is a description without quotes",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlExtendedPropertyExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.extended_properties) == 1
        ep = model.extended_properties[0]
        assert ep.value == "This is a description without quotes"


class TestEmptyValue:
    """Edge case: SqlExtendedProperty with no Value property."""

    def test_empty_value(self) -> None:
        elements_xml = _make_extended_property_element(
            "[SqlTable].[dbo].[Users].[MS_Description]",
            "[dbo].[Users]",
            value=None,
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlExtendedPropertyExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.extended_properties) == 1
        ep = model.extended_properties[0]
        assert ep.value == ""


class TestEmptyCdataValue:
    """Edge case: SqlExtendedProperty with empty CDATA value."""

    def test_empty_cdata_value(self) -> None:
        elements_xml = _make_extended_property_element(
            "[SqlTable].[dbo].[Users].[MS_Description]",
            "[dbo].[Users]",
            value="",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlExtendedPropertyExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.extended_properties) == 1
        ep = model.extended_properties[0]
        assert ep.value == ""


class TestSingleQuoteOnlyValue:
    """Edge case: Value that is just a single quote (not a pair)."""

    def test_single_quote_not_stripped(self) -> None:
        elements_xml = _make_extended_property_element(
            "[SqlTable].[dbo].[Users].[MS_Description]",
            "[dbo].[Users]",
            value="'",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlExtendedPropertyExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.extended_properties) == 1
        ep = model.extended_properties[0]
        assert ep.value == "'"


class TestMissingName:
    """Edge case: SqlExtendedProperty with no Name attribute is skipped."""

    def test_missing_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = '<Element Type="SqlExtendedProperty" />'
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlExtendedPropertyExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.extended_property"):
            model = parser.parse(content).database_model

        assert len(model.extended_properties) == 0
        assert any("no Name" in msg for msg in caplog.messages)


class TestMissingHost:
    """Edge case: SqlExtendedProperty with no Host relationship is skipped."""

    def test_missing_host_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlExtendedProperty" '
            'Name="[SqlTable].[dbo].[Users].[MS_Description]">'
            '<Property Name="Value">'
            "<Value><![CDATA['some value']]></Value>"
            "</Property>"
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlExtendedPropertyExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.extended_property"):
            model = parser.parse(content).database_model

        assert len(model.extended_properties) == 0
        assert any("no Host" in msg for msg in caplog.messages)


class TestMalformedName:
    """Edge case: SqlExtendedProperty with malformed Name is skipped."""

    def test_malformed_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlExtendedProperty" Name="not-valid-name">'
            '<Relationship Name="Host">'
            "<Entry>"
            '<References Name="[dbo].[Users]" />'
            "</Entry>"
            "</Relationship>"
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlExtendedPropertyExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.extended_property"):
            model = parser.parse(content).database_model

        assert len(model.extended_properties) == 0
        assert any("malformed Name" in msg for msg in caplog.messages)


class TestMultipleExtendedProperties:
    """Multiple extended properties are all extracted."""

    def test_multiple_extended_properties(self) -> None:
        elements_xml = (
            _make_extended_property_element(
                "[SqlTable].[dbo].[Users].[MS_Description]",
                "[dbo].[Users]",
                value="'Users table'",
            )
            + _make_extended_property_element(
                "[SqlColumn].[dbo].[Users].[Name].[MS_Description]",
                "[dbo].[Users].[Name]",
                value="User full name",
            )
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlExtendedPropertyExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.extended_properties) == 2
        assert model.extended_properties[0].value == "Users table"
        assert model.extended_properties[1].value == "User full name"


class TestExtractorElementType:
    """Verify extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlExtendedPropertyExtractor()
        assert extractor.element_type == "SqlExtendedProperty"
