"""Tests for SqlTable extractor and registration.

Maps to Spec 06 acceptance criteria for table-level behavior.
"""

from __future__ import annotations

import logging
from xml.etree.ElementTree import Element, SubElement

import pytest

from constants import DAC_NAMESPACE
from models.enums import CompressionLevel, Durability
from parsing.extractors import register_spec06_extractors
from parsing.extractors.table import SqlTableExtractor
from parsing.registry import ExtractorRegistry

_NS = DAC_NAMESPACE


def _ns(tag: str) -> str:
    return f"{{{_NS}}}{tag}"


def _add_schema_ref(table_elem: Element, schema_name: str = "[dbo]") -> None:
    """Add a Schema relationship to a table element."""
    rel = SubElement(table_elem, _ns("Relationship"), attrib={"Name": "Schema"})
    entry = SubElement(rel, _ns("Entry"))
    SubElement(entry, _ns("References"), attrib={"Name": schema_name})


def _add_simple_column(
    table_elem: Element,
    col_name: str,
    type_ref: str = "[int]",
    *,
    is_nullable: str | None = None,
    generated_always_type: str | None = None,
) -> None:
    """Add a SqlSimpleColumn to the Columns relationship of a table."""
    # Find or create the Columns relationship
    columns_rel = None
    for rel in table_elem.findall(_ns("Relationship")):
        if rel.get("Name") == "Columns":
            columns_rel = rel
            break
    if columns_rel is None:
        columns_rel = SubElement(table_elem, _ns("Relationship"), attrib={"Name": "Columns"})

    entry = SubElement(columns_rel, _ns("Entry"))
    col = SubElement(entry, _ns("Element"), attrib={"Type": "SqlSimpleColumn", "Name": col_name})

    if is_nullable is not None:
        SubElement(col, _ns("Property"), attrib={"Name": "IsNullable", "Value": is_nullable})

    if generated_always_type is not None:
        SubElement(col, _ns("Property"), attrib={"Name": "GeneratedAlwaysType", "Value": generated_always_type})

    # TypeSpecifier
    ts_rel = SubElement(col, _ns("Relationship"), attrib={"Name": "TypeSpecifier"})
    ts_entry = SubElement(ts_rel, _ns("Entry"))
    SubElement(ts_entry, _ns("References"), attrib={"Name": type_ref, "ExternalSource": "BuiltIns"})


def _add_computed_column(
    table_elem: Element,
    col_name: str,
    expression: str,
    *,
    is_persisted: str | None = None,
) -> None:
    """Add a SqlComputedColumn to the Columns relationship of a table."""
    columns_rel = None
    for rel in table_elem.findall(_ns("Relationship")):
        if rel.get("Name") == "Columns":
            columns_rel = rel
            break
    if columns_rel is None:
        columns_rel = SubElement(table_elem, _ns("Relationship"), attrib={"Name": "Columns"})

    entry = SubElement(columns_rel, _ns("Entry"))
    col = SubElement(entry, _ns("Element"), attrib={"Type": "SqlComputedColumn", "Name": col_name})

    prop = SubElement(col, _ns("Property"), attrib={"Name": "ExpressionScript"})
    value = SubElement(prop, _ns("Value"))
    value.text = expression

    if is_persisted is not None:
        SubElement(col, _ns("Property"), attrib={"Name": "IsPersisted", "Value": is_persisted})


def _build_table(
    name: str = "[Application].[Countries]",
    schema_ref: str = "[Application]",
) -> Element:
    """Build a minimal SqlTable element with schema reference."""
    table = Element(_ns("Element"), attrib={"Type": "SqlTable", "Name": name})
    _add_schema_ref(table, schema_ref)
    return table


class TestBasicTableWithColumns:
    """AC1: Table with 3 simple columns, correct ordinals."""

    def test_three_columns_ordinals(self) -> None:
        table = _build_table()
        _add_simple_column(table, "[Application].[Countries].[CountryId]")
        _add_simple_column(table, "[Application].[Countries].[CountryName]", "[nvarchar]")
        _add_simple_column(table, "[Application].[Countries].[CountryCode]", "[nvarchar]")

        extractor = SqlTableExtractor()
        results = extractor.extract([table], None)

        assert len(results) == 1
        t = results[0]
        assert t.name.parts == ("Application", "Countries")
        assert len(t.columns) == 3
        assert t.columns[0].ordinal == 0
        assert t.columns[1].ordinal == 1
        assert t.columns[2].ordinal == 2


class TestTemporalTable:
    """AC7: Temporal table with history reference and GeneratedAlwaysType columns."""

    def test_temporal_history_and_generated_columns(self) -> None:
        table = _build_table()

        # Add temporal history table relationship
        rel = SubElement(table, _ns("Relationship"), attrib={"Name": "TemporalSystemVersioningHistoryTable"})
        entry = SubElement(rel, _ns("Entry"))
        SubElement(entry, _ns("References"), attrib={"Name": "[Application].[Countries_Archive]"})

        _add_simple_column(table, "[Application].[Countries].[Id]")
        _add_simple_column(
            table,
            "[Application].[Countries].[ValidFrom]",
            "[datetime2]",
            generated_always_type="1",
        )
        _add_simple_column(
            table,
            "[Application].[Countries].[ValidTo]",
            "[datetime2]",
            generated_always_type="2",
        )

        extractor = SqlTableExtractor()
        results = extractor.extract([table], None)

        assert len(results) == 1
        t = results[0]
        assert t.temporal_history_table is not None
        assert t.temporal_history_table.parts == ("Application", "Countries_Archive")

        assert t.columns[1].generated_always_type == "1"
        assert t.columns[2].generated_always_type == "2"


class TestTableWithCompressionOptions:
    """Table with DataCompressionOptions."""

    def test_compression_options(self) -> None:
        table = _build_table()

        rel = SubElement(table, _ns("Relationship"), attrib={"Name": "DataCompressionOptions"})
        entry = SubElement(rel, _ns("Entry"))
        opt = SubElement(entry, _ns("Element"), attrib={"Type": "SqlDataCompressionOption"})
        SubElement(opt, _ns("Property"), attrib={"Name": "CompressionLevel", "Value": "2"})
        SubElement(opt, _ns("Property"), attrib={"Name": "PartitionNumber", "Value": "1"})

        extractor = SqlTableExtractor()
        results = extractor.extract([table], None)

        assert len(results) == 1
        t = results[0]
        assert len(t.compression_options) == 1
        assert t.compression_options[0].compression_level == CompressionLevel.PAGE
        assert t.compression_options[0].partition_number == 1


class TestTableWithFilegroups:
    """Table with Filegroup and FilegroupForTextImage relationships."""

    def test_filegroup_and_lob_filegroup(self) -> None:
        table = _build_table()

        fg_rel = SubElement(table, _ns("Relationship"), attrib={"Name": "Filegroup"})
        fg_entry = SubElement(fg_rel, _ns("Entry"))
        SubElement(fg_entry, _ns("References"), attrib={"Name": "[PRIMARY]"})

        lob_rel = SubElement(table, _ns("Relationship"), attrib={"Name": "FilegroupForTextImage"})
        lob_entry = SubElement(lob_rel, _ns("Entry"))
        SubElement(lob_entry, _ns("References"), attrib={"Name": "[TEXTIMAGE_ON]"})

        extractor = SqlTableExtractor()
        results = extractor.extract([table], None)

        assert len(results) == 1
        t = results[0]
        assert t.filegroup is not None
        assert t.filegroup.parts == ("PRIMARY",)
        assert t.lob_filegroup is not None
        assert t.lob_filegroup.parts == ("TEXTIMAGE_ON",)


class TestDefaultPropertyValues:
    """Default values for optional table properties."""

    def test_defaults(self) -> None:
        table = _build_table()

        extractor = SqlTableExtractor()
        results = extractor.extract([table], None)

        assert len(results) == 1
        t = results[0]
        assert t.is_ansi_nulls_on is True
        assert t.is_memory_optimized is False
        assert t.durability is None
        assert t.filegroup is None
        assert t.lob_filegroup is None
        assert t.temporal_history_table is None
        assert t.compression_options == ()
        assert t.columns == ()

    def test_explicit_property_values(self) -> None:
        table = _build_table()
        SubElement(table, _ns("Property"), attrib={"Name": "IsAnsiNullsOn", "Value": "False"})
        SubElement(table, _ns("Property"), attrib={"Name": "IsMemoryOptimized", "Value": "True"})
        SubElement(table, _ns("Property"), attrib={"Name": "Durability", "Value": "1"})

        extractor = SqlTableExtractor()
        results = extractor.extract([table], None)

        assert len(results) == 1
        t = results[0]
        assert t.is_ansi_nulls_on is False
        assert t.is_memory_optimized is True
        assert t.durability == Durability.SCHEMA_ONLY

    def test_durability_schema_and_data(self) -> None:
        table = _build_table()
        SubElement(table, _ns("Property"), attrib={"Name": "Durability", "Value": "0"})

        extractor = SqlTableExtractor()
        results = extractor.extract([table], None)

        assert results[0].durability == Durability.SCHEMA_AND_DATA


class TestMissingNameSkipsWithWarning:
    """Graceful degradation: missing Name attribute skips element."""

    def test_no_name_attribute(self, caplog: pytest.LogCaptureFixture) -> None:
        table = Element(_ns("Element"), attrib={"Type": "SqlTable"})
        _add_schema_ref(table)

        extractor = SqlTableExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([table], None)
        assert results == ()
        assert "no Name attribute" in caplog.text


class TestMissingSchemaRelationship:
    """Graceful degradation: missing Schema relationship skips element."""

    def test_no_schema_ref(self, caplog: pytest.LogCaptureFixture) -> None:
        table = Element(_ns("Element"), attrib={"Type": "SqlTable", "Name": "[dbo].[T]"})

        extractor = SqlTableExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([table], None)
        assert results == ()
        assert "no Schema relationship" in caplog.text


class TestMalformedDurability:
    """Graceful degradation: malformed Durability value."""

    def test_bad_durability(self, caplog: pytest.LogCaptureFixture) -> None:
        table = _build_table()
        SubElement(table, _ns("Property"), attrib={"Name": "Durability", "Value": "bad"})

        extractor = SqlTableExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([table], None)
        assert len(results) == 1
        assert results[0].durability is None
        assert "Malformed Durability" in caplog.text


class TestRegistration:
    """Registration function adds SqlTableExtractor to registry."""

    def test_register_spec06(self) -> None:
        registry = ExtractorRegistry()
        register_spec06_extractors(registry)
        assert "SqlTable" in registry
        assert len(registry) == 1

    def test_no_duplicate_registration(self) -> None:
        registry = ExtractorRegistry()
        register_spec06_extractors(registry)
        with pytest.raises(ValueError, match="Duplicate"):
            register_spec06_extractors(registry)


class TestTableWithMixedColumns:
    """Table with both simple and computed columns."""

    def test_mixed_columns(self) -> None:
        table = _build_table()
        _add_simple_column(table, "[Application].[Countries].[Id]")
        _add_computed_column(table, "[Application].[Countries].[FullName]", "CONCAT([First], [Last])", is_persisted="True")
        _add_simple_column(table, "[Application].[Countries].[Code]", "[nvarchar]")

        extractor = SqlTableExtractor()
        results = extractor.extract([table], None)

        assert len(results) == 1
        t = results[0]
        assert len(t.columns) == 3
        assert t.columns[0].is_computed is False
        assert t.columns[0].ordinal == 0
        assert t.columns[1].is_computed is True
        assert t.columns[1].ordinal == 1
        assert t.columns[1].expression_script == "CONCAT([First], [Last])"
        assert t.columns[1].is_persisted is True
        assert t.columns[2].is_computed is False
        assert t.columns[2].ordinal == 2
