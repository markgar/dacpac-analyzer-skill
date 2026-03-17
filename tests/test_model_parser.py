"""Tests for XmlModelParser — model.xml orchestration."""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

import pytest

from constants import DAC_NAMESPACE
from interfaces.protocols import ElementExtractor
from models.domain import Schema, TypeSpecifier
from models.enums import ElementType
from models.parsed_name import ParsedName
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


class _StubExtractor(ElementExtractor):
    """Stub extractor that records calls and returns dummy results."""

    def __init__(self, type_str: str, results: tuple[Any, ...] | None = None) -> None:
        self._type_str = type_str
        self._results = results
        self.call_count = 0

    @property
    def element_type(self) -> str:
        return self._type_str

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Any, ...]:
        self.call_count += 1
        if self._results is not None:
            return self._results
        return tuple(f"item-{i}" for i in range(len(elements)))


class _SchemaExtractor(ElementExtractor):
    """Extractor that produces real Schema domain objects."""

    @property
    def element_type(self) -> str:
        return "SqlSchema"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Schema, ...]:
        results = []
        for elem in elements:
            name_raw = elem.get("Name", "")
            parsed = ParsedName(
                raw=name_raw,
                parts=(name_raw.strip("[]"),),
                schema_name=None,
                object_name=None,
                sub_name=None,
            )
            authorizer = ParsedName(
                raw="[dbo]",
                parts=("dbo",),
                schema_name=None,
                object_name=None,
                sub_name=None,
            )
            results.append(Schema(name=parsed, authorizer=authorizer))
        return tuple(results)


class TestAC1RootAttributes:
    """AC1: GIVEN model.xml with FileFormatVersion='1.2', SchemaVersion='2.9',
    DspName='...' WHEN parsed THEN root attributes are correctly extracted."""

    def test_root_attributes_extracted(self) -> None:
        content = _make_model_xml()
        registry = ExtractorRegistry()
        parser = XmlModelParser(registry)

        result = parser.parse(content)

        assert result.format_version == "1.2"
        assert result.schema_version == "2.9"
        assert result.dsp_name == "Microsoft.Data.Tools.Schema.Sql.Sql130DatabaseSchemaProvider"

    def test_collation_attributes_on_database_options(self) -> None:
        content = _make_model_xml(
            elements_xml=(
                '<Element Type="SqlDatabaseOptions" Name="[Options]">'
                '<Property Name="Collation" Value="Latin1_General_CI_AS" />'
                '</Element>'
            ),
        )
        registry = ExtractorRegistry()
        from parsing.extractors.database_options import SqlDatabaseOptionsExtractor
        registry.register(SqlDatabaseOptionsExtractor())
        parser = XmlModelParser(registry)

        result = parser.parse(content)

        assert result.database_model.database_options is not None
        assert result.database_model.database_options.collation_lcid == "1033"
        assert result.database_model.database_options.collation_case_sensitive == "False"

    def test_root_attributes_default_to_empty_without_xml_attrs(self) -> None:
        """A model.xml without root attributes yields empty strings."""
        content = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<DataSchemaModel xmlns="{DAC_NAMESPACE}">'
            f'<Model/>'
            f'</DataSchemaModel>'
        ).encode("utf-8")
        registry = ExtractorRegistry()
        parser = XmlModelParser(registry)

        result = parser.parse(content)

        assert result.format_version == ""
        assert result.schema_version == ""
        assert result.dsp_name == ""


class TestAC7UnrecognizedType:
    """AC7: GIVEN model.xml with Type='UnrecognizedFutureType' WHEN parsed
    THEN a warning is logged and parsing completes without error."""

    def test_unknown_type_logged_and_parsing_succeeds(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        elements_xml = '<Element Type="UnrecognizedFutureType" Name="[x]" />'
        content = _make_model_xml(elements_xml=elements_xml)
        registry = ExtractorRegistry()
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.context"):
            result = parser.parse(content)

        assert result is not None
        assert any("UnrecognizedFutureType" in msg for msg in caplog.messages)


class TestAC8EmptyModel:
    """AC8: GIVEN model.xml with zero Element nodes WHEN parsed
    THEN a valid DatabaseModel is returned with all collections empty."""

    def test_zero_elements_returns_valid_empty_model(self) -> None:
        content = _make_model_xml(elements_xml="")
        registry = ExtractorRegistry()
        parser = XmlModelParser(registry)

        result = parser.parse(content)
        model = result.database_model

        assert model.schemas == ()
        assert model.tables == ()
        assert model.views == ()
        assert model.procedures == ()
        assert model.scalar_functions == ()
        assert model.inline_tvfs == ()
        assert model.sequences == ()
        assert model.table_types == ()
        assert model.roles == ()
        assert model.permissions == ()
        assert model.filegroups == ()
        assert model.partition_functions == ()
        assert model.partition_schemes == ()
        assert model.primary_keys == ()
        assert model.unique_constraints == ()
        assert model.foreign_keys == ()
        assert model.check_constraints == ()
        assert model.default_constraints == ()
        assert model.indexes == ()
        assert model.extended_properties == ()
        assert model.database_options is None


class TestNoModelElement:
    """Edge case: model.xml with no <Model> element."""

    def test_missing_model_element_returns_empty_database_model(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        content = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<DataSchemaModel xmlns="{DAC_NAMESPACE}" FileFormatVersion="1.2">'
            f"</DataSchemaModel>"
        ).encode("utf-8")
        registry = ExtractorRegistry()
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.model_parser"):
            result = parser.parse(content)

        assert result.database_model.schemas == ()
        assert result.database_model.database_options is None
        assert any("No <Model> element" in msg for msg in caplog.messages)


class TestExtractorDispatch:
    """Extractors are dispatched and results assembled into DatabaseModel."""

    def test_stub_extractor_invoked_and_results_ignored_for_unknown_field(self) -> None:
        """Extracted results for types not in _TYPE_TO_FIELD are ignored."""
        # SimpleColumn doesn't have a top-level DatabaseModel field
        elements_xml = '<Element Type="SqlSimpleColumn" Name="[dbo].[T].[C]" />'
        content = _make_model_xml(elements_xml=elements_xml)
        registry = ExtractorRegistry()
        extractor = _StubExtractor("SqlSimpleColumn")
        registry.register(extractor)
        parser = XmlModelParser(registry)

        result = parser.parse(content)

        assert extractor.call_count == 1
        # Results are produced but don't map to a top-level field
        assert result.database_model.schemas == ()

    def test_schema_extractor_populates_schemas_field(self) -> None:
        """A real Schema extractor populates the schemas field."""
        elements_xml = (
            '<Element Type="SqlSchema" Name="[dbo]" />'
            '<Element Type="SqlSchema" Name="[app]" />'
        )
        content = _make_model_xml(elements_xml=elements_xml)
        registry = ExtractorRegistry()
        registry.register(_SchemaExtractor())
        parser = XmlModelParser(registry)

        result = parser.parse(content)

        assert len(result.database_model.schemas) == 2
        assert result.database_model.schemas[0].name.raw == "[dbo]"
        assert result.database_model.schemas[1].name.raw == "[app]"


class TestIntegrationMultiElement:
    """Integration test with a realistic multi-element model.xml fragment."""

    def test_multi_type_parsing(self) -> None:
        elements_xml = (
            '<Element Type="SqlSchema" Name="[dbo]" />'
            '<Element Type="SqlSchema" Name="[sales]" />'
            '<Element Type="SqlTable" Name="[dbo].[Products]" />'
            '<Element Type="SqlTable" Name="[dbo].[Orders]" />'
            '<Element Type="SqlTable" Name="[sales].[Customers]" />'
            '<Element Type="SqlView" Name="[dbo].[vProducts]" />'
            '<Element Type="UnrecognizedFutureType" Name="[x]" />'
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        schema_ext = _SchemaExtractor()
        table_ext = _StubExtractor("SqlTable")
        registry.register(schema_ext)
        registry.register(table_ext)

        parser = XmlModelParser(registry)
        result = parser.parse(content)
        model = result.database_model

        # Schemas extracted by real extractor
        assert len(model.schemas) == 2

        # Tables extracted by stub (3 elements → 3 items)
        assert table_ext.call_count == 1

        # Views have no extractor → empty
        assert model.views == ()

        # Root attributes still extracted
        assert result.format_version == "1.2"
        assert result.schema_version == "2.9"
        # No SqlDatabaseOptions extractor or element → database_options is None
        assert model.database_options is None


class TestDatabaseOptionsCollationCaseSensitive:
    """Verify the new collation_case_sensitive field on DatabaseOptions."""

    def test_collation_case_sensitive_stored(self) -> None:
        from models.domain import DatabaseOptions

        opts = DatabaseOptions(
            collation_lcid="1033",
            collation_case_sensitive="True",
        )
        assert opts.collation_case_sensitive == "True"
        assert opts.collation_lcid == "1033"

    def test_collation_case_sensitive_defaults_to_none(self) -> None:
        from models.domain import DatabaseOptions

        opts = DatabaseOptions()
        assert opts.collation_case_sensitive is None

    def test_frozen_immutability(self) -> None:
        from models.domain import DatabaseOptions

        opts = DatabaseOptions(collation_case_sensitive="False")
        with pytest.raises(AttributeError):
            opts.collation_case_sensitive = "True"  # type: ignore[misc]
