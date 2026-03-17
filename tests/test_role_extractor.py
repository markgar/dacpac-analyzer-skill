"""Tests for SqlRoleExtractor — Spec 09, AC 1."""

from __future__ import annotations

import logging

import pytest

from constants import DAC_NAMESPACE
from models.domain import Role
from parsing.extractors.role import SqlRoleExtractor
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


def _make_role_element(name: str, authorizer: str | None = None) -> str:
    """Build a SqlRole element XML string with optional Authorizer relationship."""
    if authorizer is not None:
        rel_xml = (
            f'<Relationship Name="Authorizer">'
            f"<Entry>"
            f'<References Name="{authorizer}" />'
            f"</Entry>"
            f"</Relationship>"
        )
    else:
        rel_xml = ""
    return (
        f'<Element Type="SqlRole" Name="{name}">'
        f"{rel_xml}"
        f"</Element>"
    )


class TestAC1RoleNameAndAuthorizer:
    """AC 1: GIVEN SqlRole named [SalesReaders] with Authorizer [dbo]
    WHEN extracted THEN name.parts is ['SalesReaders'] and authorizer.parts is ['dbo']."""

    def test_name_and_authorizer_parsed(self) -> None:
        elements_xml = _make_role_element("[SalesReaders]", "[dbo]")
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlRoleExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.roles) == 1
        role = model.roles[0]
        assert role.name.parts == ("SalesReaders",)
        assert role.authorizer.parts == ("dbo",)


class TestMissingAuthorizerDefaultsToDbo:
    """Edge case: Missing Authorizer relationship defaults to [dbo]."""

    def test_missing_authorizer_defaults_to_dbo(self) -> None:
        elements_xml = _make_role_element("[Readers]")
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlRoleExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.roles) == 1
        role = model.roles[0]
        assert role.name.parts == ("Readers",)
        assert role.authorizer.parts == ("dbo",)
        assert role.authorizer.raw == "[dbo]"


class TestMissingNameSkipped:
    """Edge case: Element with no Name attribute is skipped with warning."""

    def test_missing_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = '<Element Type="SqlRole" />'
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlRoleExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.role"):
            model = parser.parse(content).database_model

        assert len(model.roles) == 0
        assert any("no Name" in msg for msg in caplog.messages)


class TestMultipleRoles:
    """Multiple roles are all extracted."""

    def test_multiple_roles(self) -> None:
        elements_xml = (
            _make_role_element("[SalesReaders]", "[dbo]")
            + _make_role_element("[Admins]", "[sa]")
            + _make_role_element("[Guests]")
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlRoleExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.roles) == 3
        names = [r.name.parts[0] for r in model.roles]
        assert names == ["SalesReaders", "Admins", "Guests"]


class TestCustomAuthorizer:
    """Role with a non-dbo authorizer."""

    def test_custom_authorizer(self) -> None:
        elements_xml = _make_role_element("[Editors]", "[admin_role]")
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlRoleExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.roles) == 1
        role = model.roles[0]
        assert role.name.parts == ("Editors",)
        assert role.authorizer.parts == ("admin_role",)


class TestExtractorElementType:
    """Verify extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlRoleExtractor()
        assert extractor.element_type == "SqlRole"
