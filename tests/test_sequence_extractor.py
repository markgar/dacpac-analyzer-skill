"""Tests for SqlSequenceExtractor — Spec 09, AC 3 & AC 4."""

from __future__ import annotations

import logging

import pytest

from constants import DAC_NAMESPACE
from models.domain import Sequence
from parsing.extractors.sequence import SqlSequenceExtractor
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


def _make_sequence_element(
    name: str,
    schema: str,
    *,
    increment: str | None = None,
    start_value: str | None = None,
    type_specifier: str | None = None,
    type_is_builtin: bool = True,
    current_value: str | None = None,
) -> str:
    """Build a SqlSequence element XML string."""
    props = ""
    if increment is not None:
        props += f'<Property Name="Increment" Value="{increment}" />'
    if start_value is not None:
        props += f'<Property Name="StartValue" Value="{start_value}" />'

    schema_rel = (
        f'<Relationship Name="Schema">'
        f"<Entry>"
        f'<References Name="{schema}" />'
        f"</Entry>"
        f"</Relationship>"
    )

    type_rel = ""
    if type_specifier is not None:
        ext_src = ' ExternalSource="BuiltIns"' if type_is_builtin else ""
        type_rel = (
            f'<Relationship Name="TypeSpecifier">'
            f"<Entry>"
            f'<References Name="{type_specifier}"{ext_src} />'
            f"</Entry>"
            f"</Relationship>"
        )

    annotation = ""
    if current_value is not None:
        annotation = (
            f'<Annotation Type="OnlinePropertyAnnotation" Name="{name}">'
            f'<Property Name="CurrentValue" Value="{current_value}" />'
            f"</Annotation>"
        )

    return (
        f'<Element Type="SqlSequence" Name="{name}">'
        f"{props}"
        f"{schema_rel}"
        f"{type_rel}"
        f"{annotation}"
        f"</Element>"
    )


class TestAC3FullSequenceWithAnnotation:
    """AC 3: GIVEN SqlSequence named [Application].[CountryID_Seq] with Increment=1,
    StartValue=1, TypeSpecifier [int], and OnlinePropertyAnnotation CurrentValue=42
    WHEN extracted THEN increment is '1', start_value is '1',
    type_specifier.type_name is 'int', and current_value is '42'."""

    def test_full_sequence_extracted(self) -> None:
        elements_xml = _make_sequence_element(
            "[Application].[CountryID_Seq]",
            "[Application]",
            increment="1",
            start_value="1",
            type_specifier="[int]",
            current_value="42",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSequenceExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.sequences) == 1
        seq = model.sequences[0]
        assert seq.name.parts == ("Application", "CountryID_Seq")
        assert seq.schema_ref.parts == ("Application",)
        assert seq.increment == "1"
        assert seq.start_value == "1"
        assert seq.type_specifier.type_name == "int"
        assert seq.type_specifier.is_builtin is True
        assert seq.current_value == "42"


class TestAC4NoAnnotation:
    """AC 4: GIVEN SqlSequence with no OnlinePropertyAnnotation
    WHEN extracted THEN current_value is None."""

    def test_no_annotation_current_value_is_none(self) -> None:
        elements_xml = _make_sequence_element(
            "[dbo].[MySeq]",
            "[dbo]",
            increment="5",
            start_value="100",
            type_specifier="[bigint]",
            current_value=None,
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSequenceExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.sequences) == 1
        seq = model.sequences[0]
        assert seq.current_value is None
        assert seq.increment == "5"
        assert seq.start_value == "100"
        assert seq.type_specifier.type_name == "bigint"


class TestMissingPropertiesDefaults:
    """Edge case: missing Increment and StartValue default to '1' and '0'."""

    def test_missing_increment_defaults_to_one(self) -> None:
        elements_xml = _make_sequence_element(
            "[dbo].[Seq1]",
            "[dbo]",
            type_specifier="[int]",
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSequenceExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.sequences) == 1
        seq = model.sequences[0]
        assert seq.increment == "1"
        assert seq.start_value == "0"


class TestMissingNameSkipped:
    """Edge case: SqlSequence with no Name attribute is skipped."""

    def test_missing_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = '<Element Type="SqlSequence" />'
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSequenceExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.sequence"):
            model = parser.parse(content).database_model

        assert len(model.sequences) == 0
        assert any("no Name" in msg for msg in caplog.messages)


class TestMissingSchemaSkipped:
    """Edge case: SqlSequence with no Schema relationship is skipped."""

    def test_missing_schema_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlSequence" Name="[dbo].[Seq1]">'
            '<Property Name="Increment" Value="1" />'
            '<Relationship Name="TypeSpecifier">'
            "<Entry>"
            '<References Name="[int]" ExternalSource="BuiltIns" />'
            "</Entry>"
            "</Relationship>"
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSequenceExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.sequence"):
            model = parser.parse(content).database_model

        assert len(model.sequences) == 0
        assert any("no Schema" in msg for msg in caplog.messages)


class TestMissingTypeSpecifierSkipped:
    """Edge case: SqlSequence with no TypeSpecifier is skipped."""

    def test_missing_type_specifier_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlSequence" Name="[dbo].[Seq1]">'
            '<Relationship Name="Schema">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSequenceExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.sequence"):
            model = parser.parse(content).database_model

        assert len(model.sequences) == 0
        assert any("no TypeSpecifier" in msg for msg in caplog.messages)


class TestMultipleSequences:
    """Multiple sequences are all extracted."""

    def test_multiple_sequences(self) -> None:
        elements_xml = (
            _make_sequence_element(
                "[dbo].[Seq1]", "[dbo]",
                increment="1", start_value="1", type_specifier="[int]",
            )
            + _make_sequence_element(
                "[app].[Seq2]", "[app]",
                increment="10", start_value="100", type_specifier="[bigint]",
                current_value="500",
            )
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlSequenceExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.sequences) == 2
        assert model.sequences[0].name.parts == ("dbo", "Seq1")
        assert model.sequences[0].current_value is None
        assert model.sequences[1].name.parts == ("app", "Seq2")
        assert model.sequences[1].current_value == "500"


class TestExtractorElementType:
    """Verify extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlSequenceExtractor()
        assert extractor.element_type == "SqlSequence"
