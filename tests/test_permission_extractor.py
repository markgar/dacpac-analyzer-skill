"""Tests for SqlPermissionStatementExtractor — Spec 09, AC 2."""

from __future__ import annotations

import logging

import pytest

from constants import DAC_NAMESPACE
from models.domain import Permission
from parsing.extractors.permission import SqlPermissionStatementExtractor
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


def _make_permission_element(
    *,
    name: str | None = None,
    permission_code: str = "4",
    grantee: str = "[SalesReaders]",
    secured_object: str | None = "[Application].[Countries]",
    secured_object_disambiguator: str | None = None,
) -> str:
    """Build a SqlPermissionStatement element XML string."""
    name_attr = f' Name="{name}"' if name is not None else ""

    prop_xml = f'<Property Name="Permission" Value="{permission_code}" />'

    grantee_xml = (
        f'<Relationship Name="Grantee">'
        f"<Entry>"
        f'<References Name="{grantee}" />'
        f"</Entry>"
        f"</Relationship>"
    )

    if secured_object is not None:
        disambiguator_attr = ""
        if secured_object_disambiguator is not None:
            disambiguator_attr = f' Disambiguator="{secured_object_disambiguator}"'
        secured_xml = (
            f'<Relationship Name="SecuredObject">'
            f"<Entry>"
            f'<References Name="{secured_object}"{disambiguator_attr} />'
            f"</Entry>"
            f"</Relationship>"
        )
    else:
        secured_xml = ""

    return (
        f'<Element Type="SqlPermissionStatement"{name_attr}>'
        f"{prop_xml}"
        f"{grantee_xml}"
        f"{secured_xml}"
        f"</Element>"
    )


class TestAC2FullPermission:
    """AC 2: GIVEN SqlPermissionStatement with Permission='4', Grantee=[SalesReaders],
    SecuredObject=[Application].[Countries]
    WHEN extracted THEN permission_code is '4', grantee.parts is ['SalesReaders'],
    secured_object.parts is ['Application', 'Countries']."""

    def test_full_permission_parsed(self) -> None:
        elements_xml = _make_permission_element(
            name="[Grant.Select.Object.[Application].[Countries].To.[SalesReaders]]",
            permission_code="4",
            grantee="[SalesReaders]",
            secured_object="[Application].[Countries]",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPermissionStatementExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.permissions) == 1
        perm = model.permissions[0]
        assert perm.permission_code == "4"
        assert perm.grantee.parts == ("SalesReaders",)
        assert perm.secured_object is not None
        assert perm.secured_object.parts == ("Application", "Countries")


class TestMissingSecuredObjectNull:
    """Edge case: Missing SecuredObject means database-level permission → null."""

    def test_missing_secured_object_is_none(self) -> None:
        elements_xml = _make_permission_element(
            permission_code="1",
            grantee="[public]",
            secured_object=None,
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPermissionStatementExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.permissions) == 1
        perm = model.permissions[0]
        assert perm.secured_object is None
        assert perm.permission_code == "1"
        assert perm.grantee.parts == ("public",)


class TestMissingNameNull:
    """Edge case: Permission with no Name attribute → name is None."""

    def test_missing_name_is_none(self) -> None:
        elements_xml = _make_permission_element(
            name=None,
            permission_code="4",
            grantee="[SalesReaders]",
            secured_object="[Application].[Countries]",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPermissionStatementExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.permissions) == 1
        perm = model.permissions[0]
        assert perm.name is None
        assert perm.permission_code == "4"


class TestSecuredObjectWithDisambiguator:
    """Edge case: SecuredObject with Disambiguator attribute is preserved."""

    def test_disambiguator_reference_preserved(self) -> None:
        elements_xml = _make_permission_element(
            permission_code="2",
            grantee="[Readers]",
            secured_object="[dbo].[MyTable]",
            secured_object_disambiguator="3",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPermissionStatementExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.permissions) == 1
        perm = model.permissions[0]
        assert perm.secured_object is not None
        assert perm.secured_object.parts == ("dbo", "MyTable")


class TestMissingPermissionPropertySkipped:
    """Edge case: Missing Permission property → element skipped with warning."""

    def test_missing_permission_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        # Build element manually without Permission property
        elements_xml = (
            '<Element Type="SqlPermissionStatement">'
            '<Relationship Name="Grantee">'
            "<Entry>"
            '<References Name="[public]" />'
            "</Entry>"
            "</Relationship>"
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPermissionStatementExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.permission"):
            model = parser.parse(content).database_model

        assert len(model.permissions) == 0
        assert any("no Permission" in msg for msg in caplog.messages)


class TestMissingGranteeSkipped:
    """Edge case: Missing Grantee relationship → element skipped with warning."""

    def test_missing_grantee_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlPermissionStatement">'
            '<Property Name="Permission" Value="4" />'
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPermissionStatementExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.permission"):
            model = parser.parse(content).database_model

        assert len(model.permissions) == 0
        assert any("no Grantee" in msg for msg in caplog.messages)


class TestMultiplePermissions:
    """Multiple permissions are all extracted."""

    def test_multiple_permissions(self) -> None:
        elements_xml = (
            _make_permission_element(
                permission_code="4",
                grantee="[SalesReaders]",
                secured_object="[Application].[Countries]",
            )
            + _make_permission_element(
                permission_code="1",
                grantee="[public]",
                secured_object=None,
            )
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlPermissionStatementExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.permissions) == 2
        codes = [p.permission_code for p in model.permissions]
        assert codes == ["4", "1"]


class TestExtractorElementType:
    """Verify extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlPermissionStatementExtractor()
        assert extractor.element_type == "SqlPermissionStatement"
