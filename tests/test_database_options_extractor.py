"""Tests for SqlDatabaseOptionsExtractor — Spec 05, AC 1 and AC 7."""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

import pytest

from constants import DAC_NAMESPACE
from models.domain import DatabaseOptions
from parsing.extractors.database_options import SqlDatabaseOptionsExtractor
from parsing.model_parser import XmlModelParser
from parsing.registry import ExtractorRegistry

_NS = f"{{{DAC_NAMESPACE}}}"

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


def _make_db_options_element(*properties: tuple[str, str]) -> str:
    """Build a SqlDatabaseOptions element XML string."""
    props_xml = "".join(
        f'<Property Name="{name}" Value="{value}" />'
        for name, value in properties
    )
    return (
        f'<Element Type="SqlDatabaseOptions" Name="[Options]">'
        f"{props_xml}"
        f"</Element>"
    )


class TestAC1PropertiesExtracted:
    """AC 1: GIVEN a model.xml with SqlDatabaseOptions having Collation and
    CompatibilityLevel WHEN extracted THEN properties dict has correct values."""

    def test_properties_dict_lookup(self) -> None:
        elements_xml = _make_db_options_element(
            ("Collation", "Latin1_General_100_CI_AS"),
            ("CompatibilityLevel", "130"),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlDatabaseOptionsExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is not None
        assert model.database_options.properties["Collation"] == "Latin1_General_100_CI_AS"
        assert model.database_options.properties["CompatibilityLevel"] == "130"

    def test_collation_lcid_merged_from_root(self) -> None:
        elements_xml = _make_db_options_element(
            ("Collation", "Latin1_General_100_CI_AS"),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlDatabaseOptionsExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is not None
        assert model.database_options.collation_lcid == "1033"
        assert model.database_options.collation_case_sensitive == "False"

    def test_multiple_properties_preserved(self) -> None:
        elements_xml = _make_db_options_element(
            ("IsAnsiNullDefaultOn", "True"),
            ("IsAnsiNullsOn", "True"),
            ("IsAnsiWarningsOn", "True"),
            ("IsFullTextEnabled", "True"),
            ("RecoveryMode", "1"),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlDatabaseOptionsExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is not None
        props = model.database_options.properties
        assert props["IsAnsiNullDefaultOn"] == "True"
        assert props["IsAnsiNullsOn"] == "True"
        assert props["IsAnsiWarningsOn"] == "True"
        assert props["IsFullTextEnabled"] == "True"
        assert props["RecoveryMode"] == "1"


class TestAC7MissingDatabaseOptions:
    """AC 7: GIVEN a model.xml with no SqlDatabaseOptions element
    WHEN extracted THEN database_options is null and no error occurs."""

    def test_missing_element_returns_none(self) -> None:
        content = _make_model_xml(elements_xml="")

        registry = ExtractorRegistry()
        registry.register(SqlDatabaseOptionsExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is None

    def test_missing_element_no_error(self) -> None:
        content = _make_model_xml(
            elements_xml='<Element Type="SqlSchema" Name="[dbo]" />'
        )

        registry = ExtractorRegistry()
        registry.register(SqlDatabaseOptionsExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is None


class TestAnnotationChildrenIgnored:
    """Edge case: Annotation children should not appear in properties dict."""

    def test_annotation_not_in_properties(self) -> None:
        elements_xml = (
            '<Element Type="SqlDatabaseOptions" Name="[Options]">'
            '<Property Name="Collation" Value="Latin1_General_CI_AS" />'
            '<Annotation Type="SomeAnnotation" />'
            '</Element>'
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlDatabaseOptionsExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is not None
        assert len(model.database_options.properties) == 1
        assert "Collation" in model.database_options.properties


class TestDisambiguatorIgnored:
    """Edge case: Disambiguator attribute on the element is ignored."""

    def test_disambiguator_attribute_does_not_affect_extraction(self) -> None:
        elements_xml = (
            '<Element Type="SqlDatabaseOptions" Name="[Options]" Disambiguator="1">'
            '<Property Name="CompatibilityLevel" Value="130" />'
            '</Element>'
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlDatabaseOptionsExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is not None
        assert model.database_options.properties["CompatibilityLevel"] == "130"


class TestCdataPropertyValue:
    """Edge case: Properties with CDATA values inside <Value> children."""

    def test_cdata_value_extracted(self) -> None:
        elements_xml = (
            '<Element Type="SqlDatabaseOptions" Name="[Options]">'
            '<Property Name="SomeScript">'
            f'<Value xmlns="{DAC_NAMESPACE}"><![CDATA[SELECT 1]]></Value>'
            '</Property>'
            '</Element>'
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlDatabaseOptionsExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is not None
        assert model.database_options.properties["SomeScript"] == "SELECT 1"


class TestExtractorElementType:
    """Verify the extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlDatabaseOptionsExtractor()
        assert extractor.element_type == "SqlDatabaseOptions"


class TestPropertyWithNoValue:
    """Edge case: Property with no Value attr and no <Value> child → empty string."""

    def test_empty_value_fallback(self) -> None:
        elements_xml = (
            '<Element Type="SqlDatabaseOptions" Name="[Options]">'
            '<Property Name="EmptyProp" />'
            '</Element>'
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlDatabaseOptionsExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is not None
        assert model.database_options.properties["EmptyProp"] == ""
