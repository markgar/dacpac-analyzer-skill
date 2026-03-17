"""Tests for SqlTableTypeExtractor — Spec 09, AC 5."""

from __future__ import annotations

import logging

import pytest

from constants import DAC_NAMESPACE
from models.domain import TableType
from parsing.extractors.table_type import SqlTableTypeExtractor
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


def _make_simple_column(name: str, type_name: str = "[int]") -> str:
    """Build a SqlTableTypeSimpleColumn inline element."""
    return (
        f'<Element Type="SqlTableTypeSimpleColumn" Name="{name}">'
        f'<Relationship Name="TypeSpecifier">'
        f"<Entry>"
        f'<References Name="{type_name}" ExternalSource="BuiltIns" />'
        f"</Entry>"
        f"</Relationship>"
        f"</Element>"
    )


def _make_pk_constraint(
    name: str,
    defining_table: str,
    column_refs: tuple[str, ...],
) -> str:
    """Build a SqlTableTypePrimaryKeyConstraint inline element."""
    col_specs = ""
    for col_ref in column_refs:
        col_specs += (
            f'<Entry><Element Type="SqlIndexedColumnSpecification">'
            f'<Relationship Name="Column">'
            f"<Entry>"
            f'<References Name="{col_ref}" />'
            f"</Entry>"
            f"</Relationship>"
            f"</Element></Entry>"
        )

    return (
        f'<Element Type="SqlTableTypePrimaryKeyConstraint" Name="{name}">'
        f'<Relationship Name="DefiningTable">'
        f"<Entry>"
        f'<References Name="{defining_table}" />'
        f"</Entry>"
        f"</Relationship>"
        f'<Relationship Name="ColumnSpecifications">'
        f"{col_specs}"
        f"</Relationship>"
        f"</Element>"
    )


def _make_table_type_element(
    name: str,
    schema: str,
    *,
    columns_xml: str = "",
    constraints_xml: str = "",
) -> str:
    """Build a SqlTableType element XML string."""
    columns_rel = ""
    if columns_xml:
        columns_rel = (
            f'<Relationship Name="Columns">'
            f"<Entry>{columns_xml}</Entry>"
            f"</Relationship>"
        )

    constraints_rel = ""
    if constraints_xml:
        constraints_rel = (
            f'<Relationship Name="Constraints">'
            f"<Entry>{constraints_xml}</Entry>"
            f"</Relationship>"
        )

    schema_rel = (
        f'<Relationship Name="Schema">'
        f"<Entry>"
        f'<References Name="{schema}" />'
        f"</Entry>"
        f"</Relationship>"
    )

    return (
        f'<Element Type="SqlTableType" Name="{name}">'
        f"{schema_rel}"
        f"{columns_rel}"
        f"{constraints_rel}"
        f"</Element>"
    )


class TestAC5TwoColumnsAndPK:
    """AC 5: GIVEN SqlTableType with 2 SqlTableTypeSimpleColumn children
    and a SqlTableTypePrimaryKeyConstraint WHEN extracted THEN columns
    has 2 entries and primary_key is a valid PrimaryKey model."""

    def test_two_columns_and_pk(self) -> None:
        col1 = _make_simple_column(
            "[dbo].[OrderLineType].[OrderID]", "[int]"
        )
        col2 = _make_simple_column(
            "[dbo].[OrderLineType].[LineNumber]", "[int]"
        )
        pk = _make_pk_constraint(
            "[dbo].[OrderLineType].[PK_OrderLineType]",
            "[dbo].[OrderLineType]",
            (
                "[dbo].[OrderLineType].[OrderID]",
                "[dbo].[OrderLineType].[LineNumber]",
            ),
        )
        # Each column in its own Entry
        columns_xml_entries = (
            f'<Relationship Name="Columns">'
            f"<Entry>{col1}</Entry>"
            f"<Entry>{col2}</Entry>"
            f"</Relationship>"
        )
        constraints_xml_entries = (
            f'<Relationship Name="Constraints">'
            f"<Entry>{pk}</Entry>"
            f"</Relationship>"
        )
        schema_rel = (
            f'<Relationship Name="Schema">'
            f"<Entry>"
            f'<References Name="[dbo]" />'
            f"</Entry>"
            f"</Relationship>"
        )
        elements_xml = (
            f'<Element Type="SqlTableType" Name="[dbo].[OrderLineType]">'
            f"{schema_rel}"
            f"{columns_xml_entries}"
            f"{constraints_xml_entries}"
            f"</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlTableTypeExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.table_types) == 1
        tt = model.table_types[0]
        assert tt.name.parts == ("dbo", "OrderLineType")
        assert tt.schema_ref.parts == ("dbo",)
        assert len(tt.columns) == 2
        assert tt.columns[0].name.parts[-1] == "OrderID"
        assert tt.columns[1].name.parts[-1] == "LineNumber"
        assert tt.primary_key is not None
        assert tt.primary_key.name.parts[-1] == "PK_OrderLineType"
        assert len(tt.primary_key.columns) == 2


class TestNoPrimaryKey:
    """Edge case: TableType with no primary key constraint."""

    def test_no_pk_is_none(self) -> None:
        col = _make_simple_column("[dbo].[MyType].[Col1]", "[nvarchar]")
        elements_xml = (
            f'<Element Type="SqlTableType" Name="[dbo].[MyType]">'
            f'<Relationship Name="Schema">'
            f"<Entry>"
            f'<References Name="[dbo]" />'
            f"</Entry>"
            f"</Relationship>"
            f'<Relationship Name="Columns">'
            f"<Entry>{col}</Entry>"
            f"</Relationship>"
            f"</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlTableTypeExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.table_types) == 1
        tt = model.table_types[0]
        assert tt.primary_key is None
        assert len(tt.columns) == 1


class TestNoColumns:
    """Edge case: TableType with no columns — empty tuple."""

    def test_no_columns_empty_tuple(self) -> None:
        elements_xml = (
            f'<Element Type="SqlTableType" Name="[dbo].[EmptyType]">'
            f'<Relationship Name="Schema">'
            f"<Entry>"
            f'<References Name="[dbo]" />'
            f"</Entry>"
            f"</Relationship>"
            f"</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlTableTypeExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.table_types) == 1
        tt = model.table_types[0]
        assert tt.columns == ()
        assert tt.primary_key is None


class TestMissingNameSkipped:
    """Edge case: SqlTableType with no Name attribute is skipped."""

    def test_missing_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = '<Element Type="SqlTableType" />'
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlTableTypeExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.table_type"):
            model = parser.parse(content).database_model

        assert len(model.table_types) == 0
        assert any("no Name" in msg for msg in caplog.messages)


class TestMissingSchemaSkipped:
    """Edge case: SqlTableType with no Schema relationship is skipped."""

    def test_missing_schema_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = '<Element Type="SqlTableType" Name="[dbo].[MyType]" />'
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlTableTypeExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.table_type"):
            model = parser.parse(content).database_model

        assert len(model.table_types) == 0
        assert any("no Schema" in msg for msg in caplog.messages)


class TestExtractorElementType:
    """Verify extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlTableTypeExtractor()
        assert extractor.element_type == "SqlTableType"


class TestMultipleTableTypes:
    """Multiple table types are all extracted."""

    def test_multiple_table_types(self) -> None:
        tt1_xml = _make_table_type_element(
            "[dbo].[Type1]", "[dbo]",
            columns_xml=_make_simple_column("[dbo].[Type1].[Col1]"),
        )
        tt2_xml = _make_table_type_element(
            "[app].[Type2]", "[app]",
            columns_xml=_make_simple_column("[app].[Type2].[Col1]"),
        )
        content = _make_model_xml(elements_xml=tt1_xml + tt2_xml)

        registry = ExtractorRegistry()
        registry.register(SqlTableTypeExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.table_types) == 2
        names = [tt.name.parts[-1] for tt in model.table_types]
        assert names == ["Type1", "Type2"]
