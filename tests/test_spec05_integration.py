"""Integration test for Spec 05 — all element types through the full pipeline.

Builds a realistic model.xml fragment containing SqlDatabaseOptions,
SqlSchema, SqlFilegroup, SqlPartitionFunction, and SqlPartitionScheme,
then parses it via ``XmlModelParser`` with all Spec 05 extractors
registered using ``register_spec05_extractors``.
"""

from __future__ import annotations

from constants import DAC_NAMESPACE
from models.enums import PartitionRange
from parsing.extractors import register_spec05_extractors
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


def _build_full_model_xml() -> bytes:
    """Build a model.xml containing all 5 Spec 05 element types."""
    # SqlDatabaseOptions
    db_options = (
        '<Element Type="SqlDatabaseOptions">'
        '<Property Name="Collation" Value="Latin1_General_100_CI_AS" />'
        '<Property Name="CompatibilityLevel" Value="130" />'
        '<Property Name="IsAnsiNullsOn" Value="True" />'
        '<Property Name="RecoveryMode" Value="1" />'
        "</Element>"
    )

    # SqlSchema elements
    schemas = (
        '<Element Type="SqlSchema" Name="[dbo]">'
        '<Relationship Name="Authorizer">'
        "<Entry>"
        '<References Name="[dbo]" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
        '<Element Type="SqlSchema" Name="[Application]">'
        '<Relationship Name="Authorizer">'
        "<Entry>"
        '<References Name="[dbo]" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
    )

    # SqlFilegroup elements
    filegroups = (
        '<Element Type="SqlFilegroup" Name="[PRIMARY]">'
        "</Element>"
        '<Element Type="SqlFilegroup" Name="[WWI_InMemory_Data]">'
        '<Property Name="ContainsMemoryOptimizedData" Value="True" />'
        "</Element>"
    )

    # SqlPartitionFunction
    partition_func = (
        '<Element Type="SqlPartitionFunction" Name="[PF_OrderDate]">'
        '<Property Name="Range" Value="2" />'
        '<Relationship Name="ParameterType">'
        "<Entry>"
        '<Element Type="SqlTypeSpecifier">'
        '<Relationship Name="Type">'
        "<Entry>"
        '<References Name="[datetime]" ExternalSource="BuiltIns" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="BoundaryValues">'
        "<Entry>"
        '<Element Type="SqlPartitionValue">'
        '<Property Name="ExpressionScript">'
        "<Value><![CDATA['20130101']]></Value>"
        "</Property>"
        "</Element>"
        "</Entry>"
        "<Entry>"
        '<Element Type="SqlPartitionValue">'
        '<Property Name="ExpressionScript">'
        "<Value><![CDATA['20140101']]></Value>"
        "</Property>"
        "</Element>"
        "</Entry>"
        "<Entry>"
        '<Element Type="SqlPartitionValue">'
        '<Property Name="ExpressionScript">'
        "<Value><![CDATA['20150101']]></Value>"
        "</Property>"
        "</Element>"
        "</Entry>"
        "</Relationship>"
        "</Element>"
    )

    # SqlPartitionScheme
    partition_scheme = (
        '<Element Type="SqlPartitionScheme" Name="[PS_OrderDate]">'
        '<Relationship Name="PartitionFunction">'
        "<Entry>"
        '<References Name="[PF_OrderDate]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="FilegroupSpecifiers">'
        "<Entry>"
        '<Element Type="SqlFilegroupSpecifier">'
        '<Relationship Name="Filegroup">'
        "<Entry>"
        '<References Name="[FG1]" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
        "</Entry>"
        "<Entry>"
        '<Element Type="SqlFilegroupSpecifier">'
        '<Relationship Name="Filegroup">'
        "<Entry>"
        '<References Name="[FG2]" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
        "</Entry>"
        "</Relationship>"
        "</Element>"
    )

    elements = db_options + schemas + filegroups + partition_func + partition_scheme

    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f"<DataSchemaModel {_ROOT_ATTRS}>"
        f"<Model>{elements}</Model>"
        f"</DataSchemaModel>"
    ).encode("utf-8")


class TestSpec05Integration:
    """Integration test: all 5 Spec 05 element types parsed through the full pipeline."""

    def test_full_pipeline(self) -> None:
        content = _build_full_model_xml()

        registry = ExtractorRegistry()
        register_spec05_extractors(registry)
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        # AC 1: DatabaseOptions properties
        assert model.database_options is not None
        props = model.database_options.properties
        assert props["Collation"] == "Latin1_General_100_CI_AS"
        assert props["CompatibilityLevel"] == "130"
        assert props["IsAnsiNullsOn"] == "True"
        assert props["RecoveryMode"] == "1"

        # Root collation attributes passed through
        assert model.database_options.collation_lcid == "1033"
        assert model.database_options.collation_case_sensitive == "False"

        # AC 2: Schemas
        assert len(model.schemas) == 2
        dbo = model.schemas[0]
        app = model.schemas[1]
        assert dbo.name.parts == ("dbo",)
        assert dbo.authorizer.parts == ("dbo",)
        assert app.name.parts == ("Application",)
        assert app.authorizer.parts == ("dbo",)

        # AC 3 & 4: Filegroups
        assert len(model.filegroups) == 2
        primary = model.filegroups[0]
        inmem = model.filegroups[1]
        assert primary.name.parts == ("PRIMARY",)
        assert primary.contains_memory_optimized_data is False
        assert inmem.name.parts == ("WWI_InMemory_Data",)
        assert inmem.contains_memory_optimized_data is True

        # AC 5: Partition function
        assert len(model.partition_functions) == 1
        pf = model.partition_functions[0]
        assert pf.name.parts == ("PF_OrderDate",)
        assert pf.range_type == PartitionRange.RIGHT
        assert pf.parameter_type.type_name == "datetime"
        assert pf.parameter_type.is_builtin is True
        assert pf.boundary_values == ("'20130101'", "'20140101'", "'20150101'")

        # AC 6: Partition scheme
        assert len(model.partition_schemes) == 1
        ps = model.partition_schemes[0]
        assert ps.name.parts == ("PS_OrderDate",)
        assert ps.partition_function.parts == ("PF_OrderDate",)
        assert len(ps.filegroups) == 2
        assert ps.filegroups[0].parts == ("FG1",)
        assert ps.filegroups[1].parts == ("FG2",)


class TestSpec05RegistrationFunction:
    """Verify register_spec05_extractors registers all 5 types."""

    def test_registers_all_types(self) -> None:
        registry = ExtractorRegistry()
        register_spec05_extractors(registry)

        assert len(registry) == 5
        assert "SqlDatabaseOptions" in registry
        assert "SqlSchema" in registry
        assert "SqlFilegroup" in registry
        assert "SqlPartitionFunction" in registry
        assert "SqlPartitionScheme" in registry

    def test_duplicate_registration_raises(self) -> None:
        """Registering twice raises ValueError."""
        import pytest

        registry = ExtractorRegistry()
        register_spec05_extractors(registry)
        with pytest.raises(ValueError, match="Duplicate"):
            register_spec05_extractors(registry)


class TestSpec05AC7MissingDbOptions:
    """AC 7: No SqlDatabaseOptions element → database_options is None."""

    def test_no_db_options(self) -> None:
        # Model with only a schema — no SqlDatabaseOptions
        elements_xml = (
            '<Element Type="SqlSchema" Name="[dbo]">'
            '<Relationship Name="Authorizer">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            "</Element>"
        )
        content = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f"<DataSchemaModel {_ROOT_ATTRS}>"
            f"<Model>{elements_xml}</Model>"
            f"</DataSchemaModel>"
        ).encode("utf-8")

        registry = ExtractorRegistry()
        register_spec05_extractors(registry)
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is None
        assert len(model.schemas) == 1


class TestSpec05EmptyModel:
    """Edge case: Empty model element with all extractors registered."""

    def test_empty_model(self) -> None:
        content = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f"<DataSchemaModel {_ROOT_ATTRS}>"
            f"<Model></Model>"
            f"</DataSchemaModel>"
        ).encode("utf-8")

        registry = ExtractorRegistry()
        register_spec05_extractors(registry)
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert model.database_options is None
        assert model.schemas == ()
        assert model.filegroups == ()
        assert model.partition_functions == ()
        assert model.partition_schemes == ()
