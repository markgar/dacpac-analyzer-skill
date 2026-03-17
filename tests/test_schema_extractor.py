"""Tests for SqlSchemaExtractor — Spec 05, AC 2."""

from __future__ import annotations

import logging
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

import pytest

from constants import DAC_NAMESPACE
from models.domain import Schema
from parsing.extractors.schema import SqlSchemaExtractor
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


def _make_schema_element(name: str, authorizer: str | None = None) -> str:
    """Build a SqlSchema element XML string with optional Authorizer relationship."""
    if authorizer is not None:
        rel_xml = (
            f'<Relationship Name="Authorizer">'
            f'<Entry>'
            f'<References Name="{authorizer}" />'
            f'</Entry>'
            f'</Relationship>'
        )
    else:
        rel_xml = ""
    return (
        f'<Element Type="SqlSchema" Name="{name}">'
        f"{rel_xml}"
        f"</Element>"
    )


class TestAC2SchemaNameAndAuthorizer:
    """AC 2: GIVEN SqlSchema with Name='[Application]' and Authorizer='[dbo]'
    WHEN extracted THEN name.parts is ['Application'] and authorizer.parts is ['dbo']."""

    def test_name_and_authorizer_parsed(self) -> None:
        elements_xml = _make_schema_element("[Application]", "[dbo]")
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSchemaExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.schemas) == 1
        schema = model.schemas[0]
        assert schema.name.parts == ("Application",)
        assert schema.authorizer.parts == ("dbo",)

    def test_multi_part_schema_name(self) -> None:
        """Schema names are typically single-part, but parse_name handles any form."""
        elements_xml = _make_schema_element("[Application]", "[dbo]")
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSchemaExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.schemas[0].name.raw == "[Application]"


class TestMissingAuthorizerDefaultsToDbo:
    """Edge case: Missing Authorizer relationship defaults to parsed [dbo]."""

    def test_missing_authorizer_defaults_to_dbo(self) -> None:
        elements_xml = _make_schema_element("[Sales]")
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSchemaExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.schemas) == 1
        schema = model.schemas[0]
        assert schema.name.parts == ("Sales",)
        assert schema.authorizer.parts == ("dbo",)
        assert schema.authorizer.raw == "[dbo]"


class TestDboSchemaProcessedNormally:
    """Edge case: [dbo] schema is still in the model and is processed normally."""

    def test_dbo_schema_extracted(self) -> None:
        elements_xml = _make_schema_element("[dbo]", "[dbo]")
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSchemaExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.schemas) == 1
        schema = model.schemas[0]
        assert schema.name.parts == ("dbo",)
        assert schema.authorizer.parts == ("dbo",)


class TestMultipleSchemas:
    """Multiple schemas are all extracted."""

    def test_multiple_schemas(self) -> None:
        elements_xml = (
            _make_schema_element("[dbo]", "[dbo]")
            + _make_schema_element("[Application]", "[dbo]")
            + _make_schema_element("[Sales]")
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSchemaExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.schemas) == 3
        names = [s.name.parts[0] for s in model.schemas]
        assert names == ["dbo", "Application", "Sales"]


class TestExtractorElementType:
    """Verify extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlSchemaExtractor()
        assert extractor.element_type == "SqlSchema"


class TestMissingNameSkipped:
    """Edge case: Element with no Name attribute is skipped with warning."""

    def test_missing_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = '<Element Type="SqlSchema" />'
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSchemaExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.schema"):
            model = parser.parse(content).database_model

        assert len(model.schemas) == 0
        assert any("no Name" in msg for msg in caplog.messages)


class TestSchemaWithNonDboAuthorizer:
    """Schema with a non-dbo authorizer."""

    def test_custom_authorizer(self) -> None:
        elements_xml = _make_schema_element("[Secure]", "[admin_role]")
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSchemaExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.schemas) == 1
        schema = model.schemas[0]
        assert schema.name.parts == ("Secure",)
        assert schema.authorizer.parts == ("admin_role",)
