"""Integration tests for Spec 09 — Security, Sequences, Table Types & Extended Properties.

Builds a model.xml fragment containing all 6 element types (SqlRole,
SqlPermissionStatement, SqlSequence, SqlTableType, SqlView,
SqlExtendedProperty), then parses via ``XmlModelParser`` with all
extractors registered. Validates that the ``DatabaseModel`` fields are
correctly populated end-to-end.
"""

from __future__ import annotations

import pytest

from constants import DAC_NAMESPACE
from parsing.extractors import (
    register_spec05_extractors,
    register_spec06_extractors,
    register_spec07_extractors,
    register_spec08_extractors,
    register_spec09_extractors,
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
    """Create a registry with all extractors (Spec 05–09)."""
    registry = ExtractorRegistry()
    register_spec05_extractors(registry)
    register_spec06_extractors(registry)
    register_spec07_extractors(registry)
    register_spec08_extractors(registry)
    register_spec09_extractors(registry)
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


# ---------------------------------------------------------------------------
# Element XML fragments for Spec 09 types
# ---------------------------------------------------------------------------

_ROLE = (
    '<Element Type="SqlRole" Name="[SalesReaders]">'
    '<Relationship Name="Authorizer">'
    "<Entry>"
    '<References Name="[dbo]" />'
    "</Entry>"
    "</Relationship>"
    "</Element>"
)

_PERMISSION = (
    '<Element Type="SqlPermissionStatement">'
    '<Property Name="Permission" Value="4" />'
    '<Relationship Name="Grantee">'
    "<Entry>"
    '<References Name="[SalesReaders]" />'
    "</Entry>"
    "</Relationship>"
    '<Relationship Name="SecuredObject">'
    "<Entry>"
    '<References Name="[Application].[Countries]" />'
    "</Entry>"
    "</Relationship>"
    "</Element>"
)

_SEQUENCE = (
    '<Element Type="SqlSequence" Name="[Application].[CountryID_Seq]">'
    '<Relationship Name="Schema">'
    "<Entry>"
    '<References Name="[Application]" />'
    "</Entry>"
    "</Relationship>"
    '<Property Name="Increment" Value="1" />'
    '<Property Name="StartValue" Value="1" />'
    '<Relationship Name="TypeSpecifier">'
    "<Entry>"
    '<References Name="[int]" ExternalSource="BuiltIns" />'
    "</Entry>"
    "</Relationship>"
    '<Annotation Type="OnlinePropertyAnnotation" Name="[Application].[CountryID_Seq]">'
    '<Property Name="CurrentValue" Value="42" />'
    "</Annotation>"
    "</Element>"
)

_SEQUENCE_NO_ANNOTATION = (
    '<Element Type="SqlSequence" Name="[Application].[OrderID_Seq]">'
    '<Relationship Name="Schema">'
    "<Entry>"
    '<References Name="[Application]" />'
    "</Entry>"
    "</Relationship>"
    '<Property Name="Increment" Value="5" />'
    '<Property Name="StartValue" Value="100" />'
    '<Relationship Name="TypeSpecifier">'
    "<Entry>"
    '<References Name="[bigint]" ExternalSource="BuiltIns" />'
    "</Entry>"
    "</Relationship>"
    "</Element>"
)

_TABLE_TYPE = (
    '<Element Type="SqlTableType" Name="[Application].[OrderLineList]">'
    '<Relationship Name="Schema">'
    "<Entry>"
    '<References Name="[Application]" />'
    "</Entry>"
    "</Relationship>"
    '<Relationship Name="Columns">'
    "<Entry>"
    '<Element Type="SqlTableTypeSimpleColumn" Name="[Application].[OrderLineList].[OrderID]">'
    '<Property Name="Ordinal" Value="1" />'
    '<Property Name="IsNullable" Value="False" />'
    '<Relationship Name="TypeSpecifier">'
    "<Entry>"
    '<References Name="[int]" ExternalSource="BuiltIns" />'
    "</Entry>"
    "</Relationship>"
    "</Element>"
    "</Entry>"
    "<Entry>"
    '<Element Type="SqlTableTypeSimpleColumn" Name="[Application].[OrderLineList].[Quantity]">'
    '<Property Name="Ordinal" Value="2" />'
    '<Relationship Name="TypeSpecifier">'
    "<Entry>"
    '<References Name="[int]" ExternalSource="BuiltIns" />'
    "</Entry>"
    "</Relationship>"
    "</Element>"
    "</Entry>"
    "</Relationship>"
    '<Relationship Name="Constraints">'
    "<Entry>"
    '<Element Type="SqlTableTypePrimaryKeyConstraint" Name="[Application].[PK_OrderLineList]">'
    '<Relationship Name="DefiningTable">'
    "<Entry>"
    '<References Name="[Application].[OrderLineList]" />'
    "</Entry>"
    "</Relationship>"
    '<Relationship Name="ColumnSpecifications">'
    "<Entry>"
    '<Element Type="SqlIndexedColumnSpecification">'
    '<Relationship Name="Column">'
    "<Entry>"
    '<References Name="[Application].[OrderLineList].[OrderID]" />'
    "</Entry>"
    "</Relationship>"
    "</Element>"
    "</Entry>"
    "</Relationship>"
    "</Element>"
    "</Entry>"
    "</Relationship>"
    "</Element>"
)

_VIEW = (
    '<Element Type="SqlView" Name="[Sales].[ActiveOrders]">'
    '<Relationship Name="Schema">'
    "<Entry>"
    '<References Name="[Sales]" />'
    "</Entry>"
    "</Relationship>"
    '<Property Name="QueryScript">'
    "<Value><![CDATA[SELECT * FROM [Sales].[Orders]]]></Value>"
    "</Property>"
    '<Relationship Name="Columns">'
    "<Entry>"
    '<Element Type="SqlComputedColumn" Name="[Sales].[ActiveOrders].[OrderID]">'
    '<Property Name="Ordinal" Value="1" />'
    "</Element>"
    "</Entry>"
    "<Entry>"
    '<Element Type="SqlComputedColumn" Name="[Sales].[ActiveOrders].[CustomerID]">'
    '<Property Name="Ordinal" Value="2" />'
    "</Element>"
    "</Entry>"
    "<Entry>"
    '<Element Type="SqlComputedColumn" Name="[Sales].[ActiveOrders].[OrderDate]">'
    '<Property Name="Ordinal" Value="3" />'
    "</Element>"
    "</Entry>"
    "</Relationship>"
    "</Element>"
)

_EXTENDED_PROPERTY_QUOTED = (
    '<Element Type="SqlExtendedProperty" '
    'Name="[SqlColumn].[Application].[Cities].[CityID].[Description]">'
    '<Relationship Name="Host">'
    "<Entry>"
    '<References Name="[Application].[Cities].[CityID]" />'
    "</Entry>"
    "</Relationship>"
    '<Property Name="Value">'
    "<Value><![CDATA['Numeric ID used for reference to a city within the database']]></Value>"
    "</Property>"
    "</Element>"
)

_EXTENDED_PROPERTY_UNQUOTED = (
    '<Element Type="SqlExtendedProperty" '
    'Name="[SqlTable].[Application].[Cities].[Info]">'
    '<Relationship Name="Host">'
    "<Entry>"
    '<References Name="[Application].[Cities]" />'
    "</Entry>"
    "</Relationship>"
    '<Property Name="Value">'
    "<Value><![CDATA[Plain text value no quotes]]></Value>"
    "</Property>"
    "</Element>"
)


# ---------------------------------------------------------------------------
# Full model builder
# ---------------------------------------------------------------------------

def _build_full_model_xml() -> bytes:
    """Build a model.xml with all Spec 09 element types."""
    elements = (
        _SCHEMA_APPLICATION
        + _SCHEMA_SALES
        + _ROLE
        + _PERMISSION
        + _SEQUENCE
        + _SEQUENCE_NO_ANNOTATION
        + _TABLE_TYPE
        + _VIEW
        + _EXTENDED_PROPERTY_QUOTED
        + _EXTENDED_PROPERTY_UNQUOTED
    )
    return _wrap_model_xml(elements)


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestSpec09Registration:
    """All spec 09 extractors are registered correctly."""

    def test_six_extractors_registered(self) -> None:
        registry = ExtractorRegistry()
        register_spec09_extractors(registry)

        assert len(registry) == 6
        assert "SqlRole" in registry
        assert "SqlPermissionStatement" in registry
        assert "SqlSequence" in registry
        assert "SqlTableType" in registry
        assert "SqlView" in registry
        assert "SqlExtendedProperty" in registry

    def test_no_duplicate_with_repeated_registration(self) -> None:
        """Verifying idempotency check — duplicate raises ValueError."""
        registry = ExtractorRegistry()
        register_spec09_extractors(registry)

        with pytest.raises(ValueError, match="Duplicate"):
            register_spec09_extractors(registry)


# ---------------------------------------------------------------------------
# AC1: SqlRole extraction
# ---------------------------------------------------------------------------

class TestSpec09AC1RoleExtraction:
    """AC1: Role [SalesReaders] with authorizer [dbo].

    GIVEN a SqlRole named [SalesReaders] with Authorizer referencing [dbo]
    WHEN extracted
    THEN Role.name.parts is ("SalesReaders",) and authorizer.parts is ("dbo",).
    """

    def test_role_name_and_authorizer(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.roles) == 1
        role = model.roles[0]
        assert role.name.parts == ("SalesReaders",)
        assert role.authorizer.parts == ("dbo",)


# ---------------------------------------------------------------------------
# AC2: SqlPermissionStatement extraction
# ---------------------------------------------------------------------------

class TestSpec09AC2PermissionExtraction:
    """AC2: Permission with code "4", grantee [SalesReaders], secured object [Application].[Countries].

    GIVEN a SqlPermissionStatement with Permission="4", Grantee referencing
    [SalesReaders], and SecuredObject referencing [Application].[Countries]
    WHEN extracted
    THEN permission_code is "4", grantee.parts is ("SalesReaders",),
         secured_object.parts is ("Application", "Countries").
    """

    def test_permission_fields(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.permissions) == 1
        perm = model.permissions[0]
        assert perm.permission_code == "4"
        assert perm.grantee.parts == ("SalesReaders",)
        assert perm.secured_object is not None
        assert perm.secured_object.parts == ("Application", "Countries")


# ---------------------------------------------------------------------------
# AC3: SqlSequence with annotation
# ---------------------------------------------------------------------------

class TestSpec09AC3SequenceWithAnnotation:
    """AC3: Sequence with Increment="1", StartValue="1", type int, CurrentValue="42".

    GIVEN a SqlSequence named [Application].[CountryID_Seq] with Increment="1",
    StartValue="1", TypeSpecifier [int], and OnlinePropertyAnnotation CurrentValue="42"
    WHEN extracted
    THEN increment is "1", start_value is "1", type_specifier.type_name is "int",
         and current_value is "42".
    """

    def test_sequence_with_current_value(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        # Find the sequence with annotation
        seq = [s for s in model.sequences if "CountryID_Seq" in s.name.parts][0]

        assert seq.increment == "1"
        assert seq.start_value == "1"
        assert seq.type_specifier.type_name == "int"
        assert seq.current_value == "42"


# ---------------------------------------------------------------------------
# AC4: SqlSequence without annotation
# ---------------------------------------------------------------------------

class TestSpec09AC4SequenceNoAnnotation:
    """AC4: Sequence with no OnlinePropertyAnnotation → current_value is None.

    GIVEN a SqlSequence with no OnlinePropertyAnnotation
    WHEN extracted
    THEN current_value is None.
    """

    def test_sequence_no_current_value(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        seq = [s for s in model.sequences if "OrderID_Seq" in s.name.parts][0]

        assert seq.current_value is None
        assert seq.increment == "5"
        assert seq.start_value == "100"


# ---------------------------------------------------------------------------
# AC5: SqlTableType with columns and PK
# ---------------------------------------------------------------------------

class TestSpec09AC5TableTypeExtraction:
    """AC5: TableType with 2 columns and a PK.

    GIVEN a SqlTableType with 2 SqlTableTypeSimpleColumn children
    and a SqlTableTypePrimaryKeyConstraint
    WHEN extracted
    THEN columns has 2 entries and primary_key is a valid PrimaryKey model.
    """

    def test_table_type_columns_and_pk(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.table_types) == 1
        tt = model.table_types[0]

        assert tt.name.parts == ("Application", "OrderLineList")
        assert len(tt.columns) == 2
        assert tt.primary_key is not None
        assert tt.primary_key.name.parts == ("Application", "PK_OrderLineList")
        assert len(tt.primary_key.columns) == 1


# ---------------------------------------------------------------------------
# AC6: SqlView extraction
# ---------------------------------------------------------------------------

class TestSpec09AC6ViewExtraction:
    """AC6: View with QueryScript and 3 computed columns.

    GIVEN a SqlView with QueryScript containing "SELECT * FROM [Sales].[Orders]"
    and 3 SqlComputedColumn children
    WHEN extracted
    THEN query_script is the SELECT statement and columns has 3 entries.
    """

    def test_view_query_and_columns(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.views) == 1
        view = model.views[0]

        assert view.name.parts == ("Sales", "ActiveOrders")
        assert view.query_script == "SELECT * FROM [Sales].[Orders]"
        assert len(view.columns) == 3


# ---------------------------------------------------------------------------
# AC7: SqlExtendedProperty with quoted value
# ---------------------------------------------------------------------------

class TestSpec09AC7ExtendedPropertyQuoted:
    """AC7: ExtendedProperty with quoted value stripped.

    GIVEN a SqlExtendedProperty with Host referencing [Application].[Cities].[CityID]
    and value 'Numeric ID...'
    WHEN extracted
    THEN host.parts is ("Application", "Cities", "CityID") and value has quotes stripped.
    """

    def test_extended_property_quoted_value(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        ep = [
            p for p in model.extended_properties
            if "CityID" in p.host.parts
        ]
        assert len(ep) == 1
        prop = ep[0]

        assert prop.host.parts == ("Application", "Cities", "CityID")
        assert prop.value == "Numeric ID used for reference to a city within the database"


# ---------------------------------------------------------------------------
# AC8: SqlExtendedProperty with unquoted value
# ---------------------------------------------------------------------------

class TestSpec09AC8ExtendedPropertyUnquoted:
    """AC8: ExtendedProperty with unquoted value as-is.

    GIVEN a SqlExtendedProperty with value CDATA containing no surrounding quotes
    WHEN extracted
    THEN value is the raw text as-is.
    """

    def test_extended_property_unquoted_value(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        ep = [
            p for p in model.extended_properties
            if p.host.parts == ("Application", "Cities")
        ]
        assert len(ep) == 1
        prop = ep[0]

        assert prop.value == "Plain text value no quotes"


# ---------------------------------------------------------------------------
# Cross-cutting: all Spec 09 fields populated
# ---------------------------------------------------------------------------

class TestSpec09AllFieldsPopulated:
    """Verify all Spec 09 DatabaseModel fields are populated end-to-end."""

    def test_all_spec09_collections(self) -> None:
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.roles) == 1
        assert len(model.permissions) == 1
        assert len(model.sequences) == 2
        assert len(model.table_types) == 1
        assert len(model.views) == 1
        assert len(model.extended_properties) == 2

    def test_schemas_also_extracted(self) -> None:
        """Verify Spec 05 extractors still work alongside Spec 09."""
        model = XmlModelParser(_make_registry()).parse(_build_full_model_xml()).database_model

        assert len(model.schemas) == 2
