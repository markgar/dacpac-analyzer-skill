"""Integration tests for Spec 07 — Constraints & Indexes.

Builds a model.xml fragment containing all constraint and index element types
(PK, unique, FK, check, default, index, columnstore index), then parses via
``XmlModelParser`` with Spec 05 + 06 + 07 extractors registered. Validates
that the ``DatabaseModel`` fields are correctly populated and that merged
index types (SqlIndex + SqlColumnStoreIndex → ``indexes``) work end-to-end.
"""

from __future__ import annotations

from constants import DAC_NAMESPACE
from models.enums import SortOrder
from parsing.extractors import (
    register_spec05_extractors,
    register_spec06_extractors,
    register_spec07_extractors,
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
    """Create a registry with Spec 05, 06, and 07 extractors."""
    registry = ExtractorRegistry()
    register_spec05_extractors(registry)
    register_spec06_extractors(registry)
    register_spec07_extractors(registry)
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

_SCHEMA_SALES = (
    '<Element Type="SqlSchema" Name="[Sales]">'
    '<Relationship Name="Authorizer">'
    "<Entry>"
    '<References Name="[dbo]" />'
    "</Entry>"
    "</Relationship>"
    "</Element>"
)

_SCHEMA_WAREHOUSE = (
    '<Element Type="SqlSchema" Name="[Warehouse]">'
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


def _column_spec(column_ref: str, *, is_descending: bool = False) -> str:
    """Build XML for a SqlIndexedColumnSpecification entry."""
    desc_prop = ""
    if is_descending:
        desc_prop = '<Property Name="IsDescending" Value="True" />'
    return (
        "<Entry>"
        '<Element Type="SqlIndexedColumnSpecification">'
        f"{desc_prop}"
        '<Relationship Name="Column">'
        "<Entry>"
        f'<References Name="{column_ref}" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
        "</Entry>"
    )


# ---------------------------------------------------------------------------
# Full model XML with all 7 constraint/index types
# ---------------------------------------------------------------------------

def _build_full_model_xml() -> bytes:
    """Build a model.xml exercising all Spec 07 acceptance criteria.

    Contains:
    - PK on [Application].[Countries] with 1 column (ascending) + filegroup
    - Unique constraint on [Application].[Countries].[CountryName]
    - FK from [Sales].[Orders].[CustomerID] → [Sales].[Customers].[CustomerID]
    - Composite FK from [Sales].[OrderLines] → [Sales].[Orders] (2 columns)
    - Check constraint on [Sales].[OrderLines] with expression [Quantity] > 0
    - Default constraint on [dbo].[Users].[Status] with expression 'Active'
    - Index on [Sales].[Orders] with 2 columns (ASC, DESC)
    - Columnstore index on [Warehouse].[ColdRoomTemperatures]
    """
    pk = (
        '<Element Type="SqlPrimaryKeyConstraint" Name="[Application].[PK_Countries]">'
        '<Relationship Name="DefiningTable">'
        "<Entry>"
        '<References Name="[Application].[Countries]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="ColumnSpecifications">'
        + _column_spec("[Application].[Countries].[CountryID]")
        + "</Relationship>"
        '<Relationship Name="Filegroup">'
        "<Entry>"
        '<References Name="[USERDATA]" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
    )

    unique = (
        '<Element Type="SqlUniqueConstraint" Name="[Application].[UQ_CountryName]">'
        '<Relationship Name="DefiningTable">'
        "<Entry>"
        '<References Name="[Application].[Countries]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="ColumnSpecifications">'
        + _column_spec("[Application].[Countries].[CountryName]")
        + "</Relationship>"
        "</Element>"
    )

    fk_simple = (
        '<Element Type="SqlForeignKeyConstraint" Name="[Sales].[FK_Orders_CustomerID]">'
        '<Relationship Name="DefiningTable">'
        "<Entry>"
        '<References Name="[Sales].[Orders]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="Columns">'
        "<Entry>"
        '<References Name="[Sales].[Orders].[CustomerID]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="ForeignTable">'
        "<Entry>"
        '<References Name="[Sales].[Customers]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="ForeignColumns">'
        "<Entry>"
        '<References Name="[Sales].[Customers].[CustomerID]" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
    )

    fk_composite = (
        '<Element Type="SqlForeignKeyConstraint" Name="[Sales].[FK_OrderLines_Composite]">'
        '<Relationship Name="DefiningTable">'
        "<Entry>"
        '<References Name="[Sales].[OrderLines]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="Columns">'
        "<Entry>"
        '<References Name="[Sales].[OrderLines].[OrderID]" />'
        "</Entry>"
        "<Entry>"
        '<References Name="[Sales].[OrderLines].[ProductID]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="ForeignTable">'
        "<Entry>"
        '<References Name="[Sales].[Orders]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="ForeignColumns">'
        "<Entry>"
        '<References Name="[Sales].[Orders].[OrderID]" />'
        "</Entry>"
        "<Entry>"
        '<References Name="[Sales].[Orders].[ProductID]" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
    )

    check = (
        '<Element Type="SqlCheckConstraint" Name="[Sales].[CK_Quantity]">'
        '<Relationship Name="DefiningTable">'
        "<Entry>"
        '<References Name="[Sales].[OrderLines]" />'
        "</Entry>"
        "</Relationship>"
        '<Property Name="CheckExpressionScript">'
        "<Value><![CDATA[[Quantity] > 0]]></Value>"
        "</Property>"
        "</Element>"
    )

    default = (
        '<Element Type="SqlDefaultConstraint" Name="[dbo].[DF_Status]">'
        '<Relationship Name="DefiningTable">'
        "<Entry>"
        '<References Name="[dbo].[Users]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="ForColumn">'
        "<Entry>"
        '<References Name="[dbo].[Users].[Status]" />'
        "</Entry>"
        "</Relationship>"
        '<Property Name="DefaultExpressionScript">'
        "<Value><![CDATA['Active']]></Value>"
        "</Property>"
        "</Element>"
    )

    index = (
        '<Element Type="SqlIndex" Name="[Sales].[IX_Orders_Date_Amount]">'
        '<Relationship Name="IndexedObject">'
        "<Entry>"
        '<References Name="[Sales].[Orders]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="ColumnSpecifications">'
        + _column_spec("[Sales].[Orders].[OrderDate]")
        + _column_spec("[Sales].[Orders].[Amount]", is_descending=True)
        + "</Relationship>"
        "</Element>"
    )

    columnstore = (
        '<Element Type="SqlColumnStoreIndex" '
        'Name="[Warehouse].[NCCX_ColdRoomTemperatures]">'
        '<Relationship Name="IndexedObject">'
        "<Entry>"
        '<References Name="[Warehouse].[ColdRoomTemperatures]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="ColumnSpecifications">'
        "</Relationship>"
        "</Element>"
    )

    elements = (
        _SCHEMA_DBO
        + _SCHEMA_APPLICATION
        + _SCHEMA_SALES
        + _SCHEMA_WAREHOUSE
        + pk
        + unique
        + fk_simple
        + fk_composite
        + check
        + default
        + index
        + columnstore
    )
    return _wrap_model_xml(elements)


# ---------------------------------------------------------------------------
# Integration tests — one class per acceptance criterion
# ---------------------------------------------------------------------------


class TestSpec07AC1PrimaryKeyExtraction:
    """AC1: PK [Application].[PK_Countries] on [Application].[Countries].

    GIVEN a SqlPrimaryKeyConstraint named [Application].[PK_Countries]
    on DefiningTable [Application].[Countries] with one column ascending
    WHEN extracted
    THEN PrimaryKey.name.parts is ("Application", "PK_Countries"),
         defining_table.parts is ("Application", "Countries"),
         columns has 1 entry with sort_order ASCENDING.
    """

    def test_primary_key_name_and_table(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.primary_keys) == 1
        pk = model.primary_keys[0]

        assert pk.name.parts == ("Application", "PK_Countries")
        assert pk.defining_table.parts == ("Application", "Countries")

    def test_primary_key_columns_ascending(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model
        pk = model.primary_keys[0]

        assert len(pk.columns) == 1
        assert pk.columns[0].sort_order == SortOrder.ASCENDING
        assert pk.columns[0].column_ref.parts == (
            "Application",
            "Countries",
            "CountryID",
        )


class TestSpec07AC2ForeignKeySingleColumn:
    """AC2: FK with Columns → [Sales].[Orders].[CustomerID] and
    ForeignColumns → [Sales].[Customers].[CustomerID].

    GIVEN a SqlForeignKeyConstraint with single-column references
    WHEN extracted
    THEN ForeignKey.columns[0].parts is ("Sales", "Orders", "CustomerID")
         and foreign_columns[0].parts is ("Sales", "Customers", "CustomerID").
    """

    def test_fk_column_parts(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        # Find the simple FK (not composite)
        simple_fk = [
            fk for fk in model.foreign_keys if len(fk.columns) == 1
        ]
        assert len(simple_fk) == 1
        fk = simple_fk[0]

        assert fk.columns[0].parts == ("Sales", "Orders", "CustomerID")
        assert fk.foreign_columns[0].parts == ("Sales", "Customers", "CustomerID")


class TestSpec07AC3CompositeForeignKey:
    """AC3: Composite FK with two local and two foreign columns.

    GIVEN a composite FK with two local columns and two foreign columns
    WHEN extracted
    THEN columns and foreign_columns each have 2 entries, positionally aligned.
    """

    def test_composite_fk_alignment(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        composite_fk = [
            fk for fk in model.foreign_keys if len(fk.columns) == 2
        ]
        assert len(composite_fk) == 1
        fk = composite_fk[0]

        assert len(fk.columns) == 2
        assert len(fk.foreign_columns) == 2

        assert fk.columns[0].parts == ("Sales", "OrderLines", "OrderID")
        assert fk.columns[1].parts == ("Sales", "OrderLines", "ProductID")
        assert fk.foreign_columns[0].parts == ("Sales", "Orders", "OrderID")
        assert fk.foreign_columns[1].parts == ("Sales", "Orders", "ProductID")


class TestSpec07AC4CheckConstraintExpression:
    """AC4: Check constraint with expression [Quantity] > 0.

    GIVEN a SqlCheckConstraint with CheckExpressionScript CDATA [Quantity] > 0
    WHEN extracted
    THEN expression is "[Quantity] > 0".
    """

    def test_check_expression(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.check_constraints) == 1
        cc = model.check_constraints[0]

        assert cc.expression == "[Quantity] > 0"
        assert cc.name.parts == ("Sales", "CK_Quantity")


class TestSpec07AC5DefaultConstraintForColumn:
    """AC5: Default constraint for column [dbo].[Users].[Status] with 'Active'.

    GIVEN a SqlDefaultConstraint for column [Schema].[Table].[Status]
    with expression 'Active'
    WHEN extracted
    THEN for_column.parts includes "Status" and expression is "'Active'".
    """

    def test_default_for_column_and_expression(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.default_constraints) == 1
        dc = model.default_constraints[0]

        assert "Status" in dc.for_column.parts
        assert dc.for_column.parts == ("dbo", "Users", "Status")
        assert dc.expression == "'Active'"


class TestSpec07AC6IndexSortOrders:
    """AC6: Index with two columns — first ascending, second descending.

    GIVEN a SqlIndex with two SqlIndexedColumnSpecification children
    WHEN extracted
    THEN columns[0].sort_order is ASCENDING and columns[1].sort_order is DESCENDING.
    """

    def test_index_column_sort_orders(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        # Find the non-columnstore index
        regular_indexes = [idx for idx in model.indexes if not idx.is_columnstore]
        assert len(regular_indexes) == 1
        idx = regular_indexes[0]

        assert len(idx.columns) == 2
        assert idx.columns[0].sort_order == SortOrder.ASCENDING
        assert idx.columns[1].sort_order == SortOrder.DESCENDING


class TestSpec07AC7ColumnStoreIndexFlag:
    """AC7: Columnstore index [Warehouse].[NCCX_ColdRoomTemperatures].

    GIVEN a SqlColumnStoreIndex named [Warehouse].[NCCX_ColdRoomTemperatures]
    WHEN extracted
    THEN Index.is_columnstore is True.
    """

    def test_columnstore_flag(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        cs_indexes = [idx for idx in model.indexes if idx.is_columnstore]
        assert len(cs_indexes) == 1
        cs = cs_indexes[0]

        assert cs.is_columnstore is True
        assert cs.name.parts == ("Warehouse", "NCCX_ColdRoomTemperatures")


class TestSpec07AC8PrimaryKeyFilegroup:
    """AC8: PK with Filegroup referencing [USERDATA].

    GIVEN a SqlPrimaryKeyConstraint with a Filegroup referencing [USERDATA]
    WHEN extracted
    THEN PrimaryKey.filegroup.parts is ("USERDATA",).
    """

    def test_pk_filegroup(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        pk = model.primary_keys[0]
        assert pk.filegroup is not None
        assert pk.filegroup.parts == ("USERDATA",)


class TestSpec07MergedIndexes:
    """Verify that SqlIndex and SqlColumnStoreIndex both merge into the
    ``indexes`` field of DatabaseModel."""

    def test_indexes_merged_count(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        # 1 regular index + 1 columnstore index = 2 total
        assert len(model.indexes) == 2

    def test_index_types_present(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        regular = [idx for idx in model.indexes if not idx.is_columnstore]
        columnstore = [idx for idx in model.indexes if idx.is_columnstore]

        assert len(regular) == 1
        assert len(columnstore) == 1


class TestSpec07AllFieldsPopulated:
    """Verify that all constraint/index fields on DatabaseModel are populated."""

    def test_all_constraint_collections(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.primary_keys) == 1
        assert len(model.unique_constraints) == 1
        assert len(model.foreign_keys) == 2
        assert len(model.check_constraints) == 1
        assert len(model.default_constraints) == 1
        assert len(model.indexes) == 2


class TestSpec07UniqueConstraintMirrorsPK:
    """Verify unique constraint has same structure as PK."""

    def test_unique_constraint_fields(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.unique_constraints) == 1
        uc = model.unique_constraints[0]

        assert uc.name.parts == ("Application", "UQ_CountryName")
        assert uc.defining_table.parts == ("Application", "Countries")
        assert len(uc.columns) == 1
        assert uc.columns[0].column_ref.parts == (
            "Application",
            "Countries",
            "CountryName",
        )
        assert uc.filegroup is None
