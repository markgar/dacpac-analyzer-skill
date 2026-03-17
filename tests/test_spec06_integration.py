"""Integration tests for Spec 06 — Table & Column Extraction.

Builds realistic model.xml fragments containing SqlTable elements with
simple and computed columns, type specifiers, temporal markers,
compression options, and various relationships, then parses them via
``XmlModelParser`` with Spec 05 + Spec 06 extractors registered.

Validates all 8 acceptance criteria end-to-end.
"""

from __future__ import annotations

from constants import DAC_NAMESPACE
from models.enums import CompressionLevel, Durability
from parsing.extractors import (
    register_spec05_extractors,
    register_spec06_extractors,
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


def _wrap_model_xml(elements: str) -> bytes:
    """Wrap element XML fragments into a complete model.xml document."""
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f"<DataSchemaModel {_ROOT_ATTRS}>"
        f"<Model>{elements}</Model>"
        f"</DataSchemaModel>"
    ).encode("utf-8")


def _make_registry() -> ExtractorRegistry:
    """Create a registry with both Spec 05 and Spec 06 extractors."""
    registry = ExtractorRegistry()
    register_spec05_extractors(registry)
    register_spec06_extractors(registry)
    return registry


# ---------------------------------------------------------------------------
# Shared XML fragment builders
# ---------------------------------------------------------------------------

_SCHEMA_APPLICATION = (
    '<Element Type="SqlSchema" Name="[Application]">'
    '<Relationship Name="Authorizer">'
    "<Entry>"
    '<References Name="[dbo]" />'
    "</Entry>"
    "</Relationship>"
    "</Element>"
)

_SCHEMA_DBO = (
    '<Element Type="SqlSchema" Name="[dbo]">'
    '<Relationship Name="Authorizer">'
    "<Entry>"
    '<References Name="[dbo]" />'
    "</Entry>"
    "</Relationship>"
    "</Element>"
)


def _simple_column(
    name: str,
    *,
    type_ref: str = "[int]",
    is_nullable: str | None = None,
    length: str | None = None,
    is_max: str | None = None,
    generated_always_type: str | None = None,
) -> str:
    """Build XML for a SqlSimpleColumn within a Columns relationship Entry."""
    props = ""
    if is_nullable is not None:
        props += f'<Property Name="IsNullable" Value="{is_nullable}" />'
    if generated_always_type is not None:
        props += f'<Property Name="GeneratedAlwaysType" Value="{generated_always_type}" />'

    facets = ""
    if length is not None:
        facets += f'<Property Name="Length" Value="{length}" />'
    if is_max is not None:
        facets += f'<Property Name="IsMax" Value="{is_max}" />'

    return (
        "<Entry>"
        f'<Element Type="SqlSimpleColumn" Name="{name}">'
        f"{props}"
        '<Relationship Name="TypeSpecifier">'
        "<Entry>"
        f"{facets}"
        f'<References Name="{type_ref}" ExternalSource="BuiltIns" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
        "</Entry>"
    )


def _computed_column(
    name: str,
    expression: str,
    *,
    is_persisted: str | None = None,
    type_ref: str | None = None,
) -> str:
    """Build XML for a SqlComputedColumn within a Columns relationship Entry."""
    props = (
        '<Property Name="ExpressionScript">'
        f"<Value><![CDATA[{expression}]]></Value>"
        "</Property>"
    )
    if is_persisted is not None:
        props += f'<Property Name="IsPersisted" Value="{is_persisted}" />'

    type_rel = ""
    if type_ref is not None:
        type_rel = (
            '<Relationship Name="TypeSpecifier">'
            "<Entry>"
            f'<References Name="{type_ref}" ExternalSource="BuiltIns" />'
            "</Entry>"
            "</Relationship>"
        )

    return (
        "<Entry>"
        f'<Element Type="SqlComputedColumn" Name="{name}">'
        f"{props}"
        f"{type_rel}"
        "</Element>"
        "</Entry>"
    )


# ---------------------------------------------------------------------------
# Full model XML for the main acceptance criteria
# ---------------------------------------------------------------------------

def _build_full_model_xml() -> bytes:
    """Build a model.xml exercising all Spec 06 acceptance criteria.

    Contains:
    - Application schema
    - Countries table with 3 simple columns + 1 computed column:
      - CountryID (int, NOT NULL)
      - CountryName (nvarchar(60), nullable)
      - Photo (varbinary(max), nullable)
      - FullName (computed, persisted)
    - Temporal history table reference
    - Temporal columns with GeneratedAlwaysType
    - Data compression options
    - Filegroup and LOB filegroup relationships
    """
    countries_table = (
        '<Element Type="SqlTable" Name="[Application].[Countries]">'
        # Schema relationship
        '<Relationship Name="Schema">'
        "<Entry>"
        '<References Name="[Application]" />'
        "</Entry>"
        "</Relationship>"
        # Properties
        '<Property Name="IsAnsiNullsOn" Value="True" />'
        '<Property Name="IsMemoryOptimized" Value="False" />'
        # Filegroup relationships
        '<Relationship Name="Filegroup">'
        "<Entry>"
        '<References Name="[PRIMARY]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="FilegroupForTextImage">'
        "<Entry>"
        '<References Name="[LOB_DATA]" />'
        "</Entry>"
        "</Relationship>"
        # Temporal history table
        '<Relationship Name="TemporalSystemVersioningHistoryTable">'
        "<Entry>"
        '<References Name="[Application].[Countries_Archive]" />'
        "</Entry>"
        "</Relationship>"
        # Columns
        '<Relationship Name="Columns">'
        + _simple_column(
            "[Application].[Countries].[CountryID]",
            type_ref="[int]",
            is_nullable="False",
        )
        + _simple_column(
            "[Application].[Countries].[CountryName]",
            type_ref="[nvarchar]",
            length="60",
        )
        + _simple_column(
            "[Application].[Countries].[Photo]",
            type_ref="[varbinary]",
            is_max="True",
        )
        + _simple_column(
            "[Application].[Countries].[ValidFrom]",
            type_ref="[datetime2]",
            is_nullable="False",
            generated_always_type="1",
        )
        + _simple_column(
            "[Application].[Countries].[ValidTo]",
            type_ref="[datetime2]",
            is_nullable="False",
            generated_always_type="2",
        )
        + _computed_column(
            "[Application].[Countries].[FullName]",
            "CONCAT([FirstName], ' ', [LastName])",
            is_persisted="True",
            type_ref="[nvarchar]",
        )
        + "</Relationship>"
        # Data compression
        '<Relationship Name="DataCompressionOptions">'
        "<Entry>"
        '<Element Type="SqlDataCompressionOption">'
        '<Property Name="CompressionLevel" Value="2" />'
        '<Property Name="PartitionNumber" Value="1" />'
        "</Element>"
        "</Entry>"
        "</Relationship>"
        "</Element>"
    )

    elements = _SCHEMA_APPLICATION + countries_table
    return _wrap_model_xml(elements)


class TestSpec06AC1TableWithThreeColumns:
    """AC1: SqlTable [Application].[Countries] with 3 SqlSimpleColumn children.

    GIVEN a SqlTable element [Application].[Countries] with 3 SqlSimpleColumn children
    WHEN extracted
    THEN Table.name.parts is ["Application", "Countries"],
         Table.columns has 3+ entries, ordinals are 0, 1, 2, ...
    """

    def test_table_name_and_column_ordinals(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        assert len(model.tables) == 1
        table = model.tables[0]

        assert table.name.parts == ("Application", "Countries")
        # 5 simple + 1 computed = 6 columns total
        assert len(table.columns) == 6
        # Ordinals are sequential starting at 0
        for i, col in enumerate(table.columns):
            assert col.ordinal == i


class TestSpec06AC2NotNullableIntColumn:
    """AC2: Column with IsNullable=False and TypeSpecifier pointing to [int].

    GIVEN a column with <Property Name="IsNullable" Value="False" /> and a
    TypeSpecifier pointing to [int]
    WHEN extracted
    THEN Column.is_nullable is False and Column.type_specifier.type_name is "int".
    """

    def test_not_nullable_int(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        country_id = table.columns[0]

        assert country_id.name.sub_name == "CountryID"
        assert country_id.is_nullable is False
        assert country_id.type_specifier.type_name == "int"


class TestSpec06AC3NullableDefault:
    """AC3: Column with no IsNullable property defaults to True.

    GIVEN a column with no IsNullable property
    WHEN extracted
    THEN Column.is_nullable is True.
    """

    def test_absent_is_nullable_defaults_true(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        # CountryName has no explicit IsNullable property
        country_name = table.columns[1]

        assert country_name.name.sub_name == "CountryName"
        assert country_name.is_nullable is True


class TestSpec06AC4ComputedColumn:
    """AC4: SqlComputedColumn with ExpressionScript and IsPersisted=True.

    GIVEN a SqlComputedColumn with ExpressionScript containing
    CONCAT([FirstName], ' ', [LastName]) and IsPersisted="True"
    WHEN extracted
    THEN Column.is_computed is True, expression_script contains the expression,
         is_persisted is True.
    """

    def test_computed_column_expression_persisted(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        full_name = table.columns[5]  # Last column

        assert full_name.name.sub_name == "FullName"
        assert full_name.is_computed is True
        assert full_name.expression_script == "CONCAT([FirstName], ' ', [LastName])"
        assert full_name.is_persisted is True


class TestSpec06AC5NvarcharTypeSpecifier:
    """AC5: TypeSpecifier referencing [nvarchar] with Length="60".

    GIVEN a table with a TypeSpecifier referencing [nvarchar] with Length="60"
    WHEN extracted
    THEN the column's type_specifier has type_name="nvarchar", length=60, is_max=False.
    """

    def test_nvarchar_60_type_specifier(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        country_name = table.columns[1]

        assert country_name.type_specifier.type_name == "nvarchar"
        assert country_name.type_specifier.length == 60
        assert country_name.type_specifier.is_max is False


class TestSpec06AC6VarbinaryMaxTypeSpecifier:
    """AC6: TypeSpecifier referencing [varbinary] with IsMax="True".

    GIVEN a table with a TypeSpecifier referencing [varbinary] with IsMax="True"
    WHEN extracted
    THEN type_specifier.is_max is True and length is null.
    """

    def test_varbinary_max(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        photo = table.columns[2]

        assert photo.name.sub_name == "Photo"
        assert photo.type_specifier.type_name == "varbinary"
        assert photo.type_specifier.is_max is True
        assert photo.type_specifier.length is None


class TestSpec06AC7TemporalTable:
    """AC7: Temporal table with history table reference and GeneratedAlwaysType.

    GIVEN a table with TemporalSystemVersioningHistoryTable referencing
    [Application].[Countries_Archive] and two columns with GeneratedAlwaysType 1 and 2
    WHEN extracted
    THEN Table.temporal_history_table.parts is ["Application", "Countries_Archive"]
         and the two columns have the correct generated_always_type values.
    """

    def test_temporal_history_table_ref(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]

        assert table.temporal_history_table is not None
        assert table.temporal_history_table.parts == ("Application", "Countries_Archive")

    def test_temporal_columns_generated_always_type(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        valid_from = table.columns[3]
        valid_to = table.columns[4]

        assert valid_from.name.sub_name == "ValidFrom"
        assert valid_from.generated_always_type == "1"

        assert valid_to.name.sub_name == "ValidTo"
        assert valid_to.generated_always_type == "2"


class TestSpec06AC8CompressionOptions:
    """AC8: DataCompressionOptions with CompressionLevel="2" and PartitionNumber="1".

    GIVEN a table with DataCompressionOptions containing an entry with
    CompressionLevel="2" and PartitionNumber="1"
    WHEN extracted
    THEN compression_options[0].compression_level is PAGE and partition_number is 1.
    """

    def test_compression_page_with_partition(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        assert len(table.compression_options) == 1
        opt = table.compression_options[0]
        assert opt.compression_level == CompressionLevel.PAGE
        assert opt.partition_number == 1


class TestSpec06RegistrationFunction:
    """Verify register_spec06_extractors registers the correct types."""

    def test_registers_sql_table(self) -> None:
        registry = ExtractorRegistry()
        register_spec06_extractors(registry)

        assert len(registry) == 1
        assert "SqlTable" in registry

    def test_duplicate_registration_raises(self) -> None:
        import pytest

        registry = ExtractorRegistry()
        register_spec06_extractors(registry)
        with pytest.raises(ValueError, match="Duplicate"):
            register_spec06_extractors(registry)


class TestSpec06TableRelationships:
    """Integration: table-level relationships (schema, filegroup, LOB filegroup)."""

    def test_schema_ref(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        assert table.schema_ref.parts == ("Application",)

    def test_filegroup(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        assert table.filegroup is not None
        assert table.filegroup.parts == ("PRIMARY",)

    def test_lob_filegroup(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        assert table.lob_filegroup is not None
        assert table.lob_filegroup.parts == ("LOB_DATA",)

    def test_ansi_nulls_and_memory_optimized(self) -> None:
        content = _build_full_model_xml()
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        assert table.is_ansi_nulls_on is True
        assert table.is_memory_optimized is False


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestSpec06TableWithZeroColumns:
    """Edge case: table with no columns."""

    def test_table_with_no_columns(self) -> None:
        table_xml = (
            '<Element Type="SqlTable" Name="[dbo].[EmptyTable]">'
            '<Relationship Name="Schema">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            "</Element>"
        )
        content = _wrap_model_xml(_SCHEMA_DBO + table_xml)
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        assert len(model.tables) == 1
        assert model.tables[0].columns == ()
        assert model.tables[0].name.parts == ("dbo", "EmptyTable")


class TestSpec06TableWithOnlyComputedColumns:
    """Edge case: table with only computed columns."""

    def test_only_computed_columns(self) -> None:
        table_xml = (
            '<Element Type="SqlTable" Name="[dbo].[CalcTable]">'
            '<Relationship Name="Schema">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            '<Relationship Name="Columns">'
            + _computed_column(
                "[dbo].[CalcTable].[A]",
                "1 + 1",
            )
            + _computed_column(
                "[dbo].[CalcTable].[B]",
                "GETDATE()",
                is_persisted="True",
            )
            + "</Relationship>"
            "</Element>"
        )
        content = _wrap_model_xml(_SCHEMA_DBO + table_xml)
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        assert len(model.tables) == 1
        table = model.tables[0]
        assert len(table.columns) == 2
        assert all(col.is_computed for col in table.columns)
        assert table.columns[0].ordinal == 0
        assert table.columns[1].ordinal == 1
        assert table.columns[1].is_persisted is True


class TestSpec06TableMissingOptionalRelationships:
    """Edge case: table with no optional relationships (filegroup, lob, temporal, compression)."""

    def test_missing_optional_relationships(self) -> None:
        table_xml = (
            '<Element Type="SqlTable" Name="[dbo].[MinimalTable]">'
            '<Relationship Name="Schema">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            '<Relationship Name="Columns">'
            + _simple_column("[dbo].[MinimalTable].[Id]", type_ref="[int]", is_nullable="False")
            + "</Relationship>"
            "</Element>"
        )
        content = _wrap_model_xml(_SCHEMA_DBO + table_xml)
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        assert len(model.tables) == 1
        table = model.tables[0]
        assert table.filegroup is None
        assert table.lob_filegroup is None
        assert table.temporal_history_table is None
        assert table.compression_options == ()
        assert table.durability is None
        assert table.is_memory_optimized is False
        assert table.is_ansi_nulls_on is True  # Default


class TestSpec06MultipleTables:
    """Edge case: multiple tables in the same model."""

    def test_multiple_tables_parsed(self) -> None:
        table1 = (
            '<Element Type="SqlTable" Name="[dbo].[Table1]">'
            '<Relationship Name="Schema">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            '<Relationship Name="Columns">'
            + _simple_column("[dbo].[Table1].[Id]", type_ref="[int]", is_nullable="False")
            + "</Relationship>"
            "</Element>"
        )
        table2 = (
            '<Element Type="SqlTable" Name="[dbo].[Table2]">'
            '<Relationship Name="Schema">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            '<Relationship Name="Columns">'
            + _simple_column("[dbo].[Table2].[Name]", type_ref="[nvarchar]", length="100")
            + _simple_column("[dbo].[Table2].[Active]", type_ref="[bit]")
            + "</Relationship>"
            "</Element>"
        )
        content = _wrap_model_xml(_SCHEMA_DBO + table1 + table2)
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        assert len(model.tables) == 2
        assert model.tables[0].name.object_name == "Table1"
        assert len(model.tables[0].columns) == 1
        assert model.tables[1].name.object_name == "Table2"
        assert len(model.tables[1].columns) == 2


class TestSpec06MemoryOptimizedTableWithDurability:
    """Edge case: memory-optimized table with durability setting."""

    def test_memory_optimized_schema_and_data(self) -> None:
        table_xml = (
            '<Element Type="SqlTable" Name="[dbo].[HotTable]">'
            '<Relationship Name="Schema">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            '<Property Name="IsMemoryOptimized" Value="True" />'
            '<Property Name="Durability" Value="0" />'
            "</Element>"
        )
        content = _wrap_model_xml(_SCHEMA_DBO + table_xml)
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        assert table.is_memory_optimized is True
        assert table.durability == Durability.SCHEMA_AND_DATA

    def test_memory_optimized_schema_only(self) -> None:
        table_xml = (
            '<Element Type="SqlTable" Name="[dbo].[TempTable]">'
            '<Relationship Name="Schema">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            '<Property Name="IsMemoryOptimized" Value="True" />'
            '<Property Name="Durability" Value="1" />'
            "</Element>"
        )
        content = _wrap_model_xml(_SCHEMA_DBO + table_xml)
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        table = model.tables[0]
        assert table.is_memory_optimized is True
        assert table.durability == Durability.SCHEMA_ONLY


class TestSpec06EmptyModelWithSpec06Extractors:
    """Edge case: empty model with Spec 06 extractors registered."""

    def test_empty_model_no_tables(self) -> None:
        content = _wrap_model_xml("")
        parser = XmlModelParser(_make_registry())
        model = parser.parse(content).database_model

        assert model.tables == ()
