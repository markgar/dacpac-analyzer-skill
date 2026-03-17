"""Tests for column, parameter, function body, and compression option extraction helpers.

Maps to Spec 06 and Spec 08 acceptance criteria for column-level,
parameter-level, and function-body-level behavior.
"""

from __future__ import annotations

import logging
from xml.etree.ElementTree import Element, SubElement, fromstring

import pytest

from constants import DAC_NAMESPACE
from models.enums import CompressionLevel
from parsing.extractors.column_helpers import (
    extract_columns,
    extract_compression_options,
    extract_computed_column,
    extract_function_body,
    extract_parameters,
    extract_simple_column,
)

_NS = DAC_NAMESPACE


def _ns(tag: str) -> str:
    """Return a namespace-qualified tag."""
    return f"{{{_NS}}}{tag}"


def _build_simple_column_xml(
    name: str,
    *,
    is_nullable: str | None = None,
    type_ref_name: str | None = None,
    type_is_builtin: bool = True,
    type_length: str | None = None,
    type_is_max: str | None = None,
    type_precision: str | None = None,
    type_scale: str | None = None,
    generated_always_type: str | None = None,
) -> Element:
    """Build a minimal SqlSimpleColumn XML element."""
    elem = Element(_ns("Element"), attrib={"Type": "SqlSimpleColumn", "Name": name})

    if is_nullable is not None:
        SubElement(elem, _ns("Property"), attrib={"Name": "IsNullable", "Value": is_nullable})

    if generated_always_type is not None:
        SubElement(elem, _ns("Property"), attrib={"Name": "GeneratedAlwaysType", "Value": generated_always_type})

    if type_ref_name is not None:
        rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "TypeSpecifier"})
        entry = SubElement(rel, _ns("Entry"))
        ref_attrib = {"Name": type_ref_name}
        if type_is_builtin:
            ref_attrib["ExternalSource"] = "BuiltIns"
        SubElement(entry, _ns("References"), attrib=ref_attrib)

        if type_length is not None:
            SubElement(entry, _ns("Property"), attrib={"Name": "Length", "Value": type_length})
        if type_is_max is not None:
            SubElement(entry, _ns("Property"), attrib={"Name": "IsMax", "Value": type_is_max})
        if type_precision is not None:
            SubElement(entry, _ns("Property"), attrib={"Name": "Precision", "Value": type_precision})
        if type_scale is not None:
            SubElement(entry, _ns("Property"), attrib={"Name": "Scale", "Value": type_scale})

    return elem


def _build_computed_column_xml(
    name: str,
    *,
    expression: str | None = None,
    is_persisted: str | None = None,
    type_ref_name: str | None = None,
    type_is_builtin: bool = True,
) -> Element:
    """Build a minimal SqlComputedColumn XML element."""
    elem = Element(_ns("Element"), attrib={"Type": "SqlComputedColumn", "Name": name})

    if expression is not None:
        prop = SubElement(elem, _ns("Property"), attrib={"Name": "ExpressionScript"})
        value = SubElement(prop, _ns("Value"))
        value.text = expression

    if is_persisted is not None:
        SubElement(elem, _ns("Property"), attrib={"Name": "IsPersisted", "Value": is_persisted})

    if type_ref_name is not None:
        rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "TypeSpecifier"})
        entry = SubElement(rel, _ns("Entry"))
        ref_attrib = {"Name": type_ref_name}
        if type_is_builtin:
            ref_attrib["ExternalSource"] = "BuiltIns"
        SubElement(entry, _ns("References"), attrib=ref_attrib)

    return elem


class TestNullableDefaultTrue:
    """AC3: Column with no IsNullable property defaults to True."""

    def test_absent_is_nullable_defaults_to_true(self) -> None:
        elem = _build_simple_column_xml(
            "[dbo].[T].[Col1]",
            type_ref_name="[int]",
        )
        col = extract_simple_column(elem, 0)
        assert col is not None
        assert col.is_nullable is True

    def test_explicit_true_is_nullable(self) -> None:
        elem = _build_simple_column_xml(
            "[dbo].[T].[Col1]",
            is_nullable="True",
            type_ref_name="[int]",
        )
        col = extract_simple_column(elem, 0)
        assert col is not None
        assert col.is_nullable is True


class TestExplicitNotNullWithIntType:
    """AC2: Column with IsNullable=False and TypeSpecifier pointing to [int]."""

    def test_not_nullable_int_column(self) -> None:
        elem = _build_simple_column_xml(
            "[dbo].[T].[Id]",
            is_nullable="False",
            type_ref_name="[int]",
        )
        col = extract_simple_column(elem, 0)
        assert col is not None
        assert col.is_nullable is False
        assert col.type_specifier.type_name == "int"
        assert col.is_computed is False


class TestComputedColumnWithExpression:
    """AC4: Computed column with ExpressionScript and IsPersisted=True."""

    def test_computed_column_expression_persisted(self) -> None:
        expr = "CONCAT([FirstName], ' ', [LastName])"
        elem = _build_computed_column_xml(
            "[dbo].[T].[FullName]",
            expression=expr,
            is_persisted="True",
        )
        col = extract_computed_column(elem, 0)
        assert col is not None
        assert col.is_computed is True
        assert col.expression_script == expr
        assert col.is_persisted is True

    def test_computed_column_not_persisted_by_default(self) -> None:
        elem = _build_computed_column_xml(
            "[dbo].[T].[Calc]",
            expression="[A] + [B]",
        )
        col = extract_computed_column(elem, 0)
        assert col is not None
        assert col.is_persisted is False


class TestComputedColumnWithoutTypeSpecifier:
    """Computed column without TypeSpecifier gets type_specifier=None."""

    def test_absent_type_specifier_is_none(self) -> None:
        elem = _build_computed_column_xml(
            "[dbo].[T].[Calc]",
            expression="[A] + [B]",
        )
        col = extract_computed_column(elem, 0)
        assert col is not None
        assert col.type_specifier is None

    def test_computed_column_with_type_specifier(self) -> None:
        elem = _build_computed_column_xml(
            "[dbo].[T].[Calc]",
            expression="[A] + [B]",
            type_ref_name="[int]",
        )
        col = extract_computed_column(elem, 0)
        assert col is not None
        assert col.type_specifier.type_name == "int"


class TestNvarcharTypeSpecifier:
    """AC5: nvarchar(60) type specifier."""

    def test_nvarchar_60(self) -> None:
        elem = _build_simple_column_xml(
            "[dbo].[T].[Name]",
            type_ref_name="[nvarchar]",
            type_length="60",
        )
        col = extract_simple_column(elem, 0)
        assert col is not None
        assert col.type_specifier.type_name == "nvarchar"
        assert col.type_specifier.length == 60
        assert col.type_specifier.is_max is False


class TestVarbinaryMaxTypeSpecifier:
    """AC6: varbinary(max) type specifier."""

    def test_varbinary_max(self) -> None:
        elem = _build_simple_column_xml(
            "[dbo].[T].[Data]",
            type_ref_name="[varbinary]",
            type_is_max="True",
        )
        col = extract_simple_column(elem, 0)
        assert col is not None
        assert col.type_specifier.type_name == "varbinary"
        assert col.type_specifier.is_max is True
        assert col.type_specifier.length is None


class TestGeneratedAlwaysType:
    """AC7 (column part): Temporal columns with GeneratedAlwaysType."""

    def test_row_start(self) -> None:
        elem = _build_simple_column_xml(
            "[dbo].[T].[ValidFrom]",
            type_ref_name="[datetime2]",
            generated_always_type="1",
        )
        col = extract_simple_column(elem, 0)
        assert col is not None
        assert col.generated_always_type == "1"

    def test_row_end(self) -> None:
        elem = _build_simple_column_xml(
            "[dbo].[T].[ValidTo]",
            type_ref_name="[datetime2]",
            generated_always_type="2",
        )
        col = extract_simple_column(elem, 0)
        assert col is not None
        assert col.generated_always_type == "2"

    def test_no_generated_always_type(self) -> None:
        elem = _build_simple_column_xml(
            "[dbo].[T].[Col1]",
            type_ref_name="[int]",
        )
        col = extract_simple_column(elem, 0)
        assert col is not None
        assert col.generated_always_type is None


class TestCompressionOptions:
    """AC8: DataCompressionOptions with PAGE level and partition number."""

    def test_page_compression_with_partition(self) -> None:
        table_elem = Element(_ns("Element"), attrib={"Type": "SqlTable", "Name": "[dbo].[T]"})
        rel = SubElement(table_elem, _ns("Relationship"), attrib={"Name": "DataCompressionOptions"})
        entry = SubElement(rel, _ns("Entry"))
        opt = SubElement(entry, _ns("Element"), attrib={"Type": "SqlDataCompressionOption"})
        SubElement(opt, _ns("Property"), attrib={"Name": "CompressionLevel", "Value": "2"})
        SubElement(opt, _ns("Property"), attrib={"Name": "PartitionNumber", "Value": "1"})

        options = extract_compression_options(table_elem)
        assert len(options) == 1
        assert options[0].compression_level == CompressionLevel.PAGE
        assert options[0].partition_number == 1

    def test_row_compression_no_partition(self) -> None:
        table_elem = Element(_ns("Element"), attrib={"Type": "SqlTable", "Name": "[dbo].[T]"})
        rel = SubElement(table_elem, _ns("Relationship"), attrib={"Name": "DataCompressionOptions"})
        entry = SubElement(rel, _ns("Entry"))
        opt = SubElement(entry, _ns("Element"), attrib={"Type": "SqlDataCompressionOption"})
        SubElement(opt, _ns("Property"), attrib={"Name": "CompressionLevel", "Value": "1"})

        options = extract_compression_options(table_elem)
        assert len(options) == 1
        assert options[0].compression_level == CompressionLevel.ROW
        assert options[0].partition_number is None

    def test_no_compression_options(self) -> None:
        table_elem = Element(_ns("Element"), attrib={"Type": "SqlTable", "Name": "[dbo].[T]"})
        options = extract_compression_options(table_elem)
        assert options == ()

    def test_malformed_compression_level(self, caplog: pytest.LogCaptureFixture) -> None:
        table_elem = Element(_ns("Element"), attrib={"Type": "SqlTable", "Name": "[dbo].[T]"})
        rel = SubElement(table_elem, _ns("Relationship"), attrib={"Name": "DataCompressionOptions"})
        entry = SubElement(rel, _ns("Entry"))
        opt = SubElement(entry, _ns("Element"), attrib={"Type": "SqlDataCompressionOption"})
        SubElement(opt, _ns("Property"), attrib={"Name": "CompressionLevel", "Value": "bad"})

        with caplog.at_level(logging.WARNING):
            options = extract_compression_options(table_elem)
        assert len(options) == 1
        assert options[0].compression_level == CompressionLevel.NONE
        assert "Malformed CompressionLevel" in caplog.text

    def test_malformed_partition_number(self, caplog: pytest.LogCaptureFixture) -> None:
        table_elem = Element(_ns("Element"), attrib={"Type": "SqlTable", "Name": "[dbo].[T]"})
        rel = SubElement(table_elem, _ns("Relationship"), attrib={"Name": "DataCompressionOptions"})
        entry = SubElement(rel, _ns("Entry"))
        opt = SubElement(entry, _ns("Element"), attrib={"Type": "SqlDataCompressionOption"})
        SubElement(opt, _ns("Property"), attrib={"Name": "CompressionLevel", "Value": "0"})
        SubElement(opt, _ns("Property"), attrib={"Name": "PartitionNumber", "Value": "abc"})

        with caplog.at_level(logging.WARNING):
            options = extract_compression_options(table_elem)
        assert len(options) == 1
        assert options[0].partition_number is None
        assert "Malformed PartitionNumber" in caplog.text


class TestExtractColumns:
    """Tests for the extract_columns dispatcher."""

    def test_mixed_column_types_in_order(self) -> None:
        col1 = _build_simple_column_xml("[dbo].[T].[A]", type_ref_name="[int]")
        col2 = _build_computed_column_xml("[dbo].[T].[B]", expression="[A] * 2")
        col3 = _build_simple_column_xml("[dbo].[T].[C]", type_ref_name="[bit]")

        columns = extract_columns((col1, col2, col3))
        assert len(columns) == 3
        assert columns[0].ordinal == 0
        assert columns[0].name.sub_name == "A"
        assert columns[0].is_computed is False
        assert columns[1].ordinal == 1
        assert columns[1].name.sub_name == "B"
        assert columns[1].is_computed is True
        assert columns[2].ordinal == 2
        assert columns[2].name.sub_name == "C"
        assert columns[2].is_computed is False

    def test_empty_columns(self) -> None:
        columns = extract_columns(())
        assert columns == ()

    def test_unknown_column_type_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        elem = Element(_ns("Element"), attrib={"Type": "SqlUnknownColumn", "Name": "[dbo].[T].[X]"})
        with caplog.at_level(logging.WARNING):
            columns = extract_columns((elem,))
        assert columns == ()
        assert "Unknown column type" in caplog.text


class TestMissingNameAttribute:
    """Graceful degradation when Name attribute is absent."""

    def test_simple_column_no_name(self, caplog: pytest.LogCaptureFixture) -> None:
        elem = Element(_ns("Element"), attrib={"Type": "SqlSimpleColumn"})
        with caplog.at_level(logging.WARNING):
            col = extract_simple_column(elem, 0)
        assert col is None
        assert "no Name attribute" in caplog.text

    def test_computed_column_no_name(self, caplog: pytest.LogCaptureFixture) -> None:
        elem = Element(_ns("Element"), attrib={"Type": "SqlComputedColumn"})
        with caplog.at_level(logging.WARNING):
            col = extract_computed_column(elem, 0)
        assert col is None
        assert "no Name attribute" in caplog.text


class TestComputedColumnIsNullable:
    """Computed columns default to is_nullable=True."""

    def test_computed_column_is_nullable_true(self) -> None:
        elem = _build_computed_column_xml("[dbo].[T].[Calc]", expression="1+1")
        col = extract_computed_column(elem, 0)
        assert col is not None
        assert col.is_nullable is True


class TestSimpleColumnMissingTypeSpecifier:
    """Simple column without TypeSpecifier gets type_specifier=None with warning."""

    def test_missing_type_specifier_is_none(self, caplog: pytest.LogCaptureFixture) -> None:
        elem = _build_simple_column_xml("[dbo].[T].[Col1]")
        with caplog.at_level(logging.WARNING):
            col = extract_simple_column(elem, 0)
        assert col is not None
        assert col.type_specifier is None
        assert "no TypeSpecifier" in caplog.text


# --- Parameter extraction helpers ---


def _build_parameter_xml(
    parent: Element,
    name: str,
    *,
    is_output: str | None = None,
    type_ref_name: str | None = None,
    type_is_builtin: bool = True,
    type_length: str | None = None,
    element_type: str = "SqlSubroutineParameter",
) -> None:
    """Add a SqlSubroutineParameter to the Parameters relationship of a parent."""
    params_rel = None
    for rel in parent.findall(_ns("Relationship")):
        if rel.get("Name") == "Parameters":
            params_rel = rel
            break
    if params_rel is None:
        params_rel = SubElement(parent, _ns("Relationship"), attrib={"Name": "Parameters"})

    entry = SubElement(params_rel, _ns("Entry"))
    param = SubElement(entry, _ns("Element"), attrib={"Type": element_type, "Name": name})

    if is_output is not None:
        SubElement(param, _ns("Property"), attrib={"Name": "IsOutput", "Value": is_output})

    if type_ref_name is not None:
        ts_rel = SubElement(param, _ns("Relationship"), attrib={"Name": "Type"})
        ts_entry = SubElement(ts_rel, _ns("Entry"))
        ref_attrib = {"Name": type_ref_name}
        if type_is_builtin:
            ref_attrib["ExternalSource"] = "BuiltIns"
        SubElement(ts_entry, _ns("References"), attrib=ref_attrib)
        if type_length is not None:
            SubElement(ts_entry, _ns("Property"), attrib={"Name": "Length", "Value": type_length})


class TestExtractParametersInputOutput:
    """AC1 (Spec 08): Parameters with is_output=True and is_output=False."""

    def test_two_params_input_and_output(self) -> None:
        parent = Element(_ns("Element"), attrib={"Type": "SqlProcedure", "Name": "[Website].[ActivateWebsiteLogon]"})
        _build_parameter_xml(
            parent, "[Website].[ActivateWebsiteLogon].[@LogonName]",
            type_ref_name="[nvarchar]", type_length="256",
        )
        _build_parameter_xml(
            parent, "[Website].[ActivateWebsiteLogon].[@Result]",
            is_output="True", type_ref_name="[nvarchar]", type_length="max",
        )

        params = extract_parameters(parent)
        assert len(params) == 2
        assert params[0].is_output is False
        assert params[0].name.sub_name == "@LogonName"
        assert params[1].is_output is True
        assert params[1].name.sub_name == "@Result"


class TestExtractParametersDefaultIsOutputFalse:
    """Parameter with absent IsOutput defaults to False."""

    def test_absent_is_output_defaults_false(self) -> None:
        parent = Element(_ns("Element"), attrib={"Type": "SqlProcedure", "Name": "[dbo].[Proc1]"})
        _build_parameter_xml(
            parent, "[dbo].[Proc1].[@Param1]",
            type_ref_name="[int]",
        )

        params = extract_parameters(parent)
        assert len(params) == 1
        assert params[0].is_output is False


class TestExtractParametersEmpty:
    """AC8 (Spec 08): Empty parameters list extracts without error."""

    def test_no_parameters_relationship(self) -> None:
        parent = Element(_ns("Element"), attrib={"Type": "SqlScalarFunction", "Name": "[dbo].[Fn1]"})
        params = extract_parameters(parent)
        assert params == ()


class TestExtractParametersWithTypeSpecifier:
    """Parameter type specifier facets are extracted correctly."""

    def test_nvarchar_with_length(self) -> None:
        parent = Element(_ns("Element"), attrib={"Type": "SqlProcedure", "Name": "[dbo].[P]"})
        _build_parameter_xml(
            parent, "[dbo].[P].[@Name]",
            type_ref_name="[nvarchar]", type_length="100",
        )

        params = extract_parameters(parent)
        assert len(params) == 1
        assert params[0].type_specifier.type_name == "nvarchar"
        assert params[0].type_specifier.length == 100
        assert params[0].type_specifier.is_builtin is True


class TestExtractParametersMissingTypeSpecifier:
    """Parameter without TypeSpecifier is skipped with warning."""

    def test_missing_type_specifier_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        parent = Element(_ns("Element"), attrib={"Type": "SqlProcedure", "Name": "[dbo].[P]"})
        _build_parameter_xml(parent, "[dbo].[P].[@Param1]")

        with caplog.at_level(logging.WARNING):
            params = extract_parameters(parent)
        assert params == ()
        assert "no TypeSpecifier" in caplog.text


class TestExtractParametersMissingName:
    """Parameter without Name attribute is skipped with warning."""

    def test_missing_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        parent = Element(_ns("Element"), attrib={"Type": "SqlProcedure", "Name": "[dbo].[P]"})
        params_rel = SubElement(parent, _ns("Relationship"), attrib={"Name": "Parameters"})
        entry = SubElement(params_rel, _ns("Entry"))
        SubElement(entry, _ns("Element"), attrib={"Type": "SqlSubroutineParameter"})

        with caplog.at_level(logging.WARNING):
            params = extract_parameters(parent)
        assert params == ()
        assert "no Name attribute" in caplog.text


class TestExtractParametersUnknownType:
    """Unknown parameter element type is skipped with warning."""

    def test_unknown_type_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        parent = Element(_ns("Element"), attrib={"Type": "SqlProcedure", "Name": "[dbo].[P]"})
        _build_parameter_xml(
            parent, "[dbo].[P].[@Param1]",
            type_ref_name="[int]",
            element_type="SqlUnknownParam",
        )

        with caplog.at_level(logging.WARNING):
            params = extract_parameters(parent)
        assert params == ()
        assert "Unexpected parameter type" in caplog.text


class TestExtractParametersDocumentOrder:
    """Parameters are collected in document order."""

    def test_three_params_in_order(self) -> None:
        parent = Element(_ns("Element"), attrib={"Type": "SqlProcedure", "Name": "[dbo].[P]"})
        _build_parameter_xml(parent, "[dbo].[P].[@A]", type_ref_name="[int]")
        _build_parameter_xml(parent, "[dbo].[P].[@B]", type_ref_name="[nvarchar]", type_length="50")
        _build_parameter_xml(parent, "[dbo].[P].[@C]", type_ref_name="[bit]")

        params = extract_parameters(parent)
        assert len(params) == 3
        assert params[0].name.sub_name == "@A"
        assert params[1].name.sub_name == "@B"
        assert params[2].name.sub_name == "@C"


# --- extract_function_body tests ---


def _build_function_body(
    parent: Element,
    body_text: str,
    *,
    dependencies: tuple[str, ...] = (),
    impl_type: str = "SqlScriptFunctionImplementation",
) -> None:
    """Add a FunctionBody relationship with SqlScriptFunctionImplementation."""
    rel = SubElement(parent, _ns("Relationship"), attrib={"Name": "FunctionBody"})
    entry = SubElement(rel, _ns("Entry"))
    impl = SubElement(entry, _ns("Element"), attrib={"Type": impl_type})

    prop = SubElement(impl, _ns("Property"), attrib={"Name": "BodyScript"})
    value = SubElement(prop, _ns("Value"))
    value.text = body_text

    if dependencies:
        dep_rel = SubElement(
            impl, _ns("Relationship"), attrib={"Name": "BodyDependencies"}
        )
        for dep_name in dependencies:
            dep_entry = SubElement(dep_rel, _ns("Entry"))
            SubElement(dep_entry, _ns("References"), attrib={"Name": dep_name})


class TestExtractFunctionBodyWithScript:
    """Function body with CDATA script text."""

    def test_body_script_extracted(self) -> None:
        parent = Element(
            _ns("Element"),
            attrib={"Type": "SqlScalarFunction", "Name": "[dbo].[F]"},
        )
        _build_function_body(parent, "RETURN @result")

        body_script, body_deps = extract_function_body(parent)
        assert body_script == "RETURN @result"
        assert body_deps == ()


class TestExtractFunctionBodyWithDependencies:
    """Function body with BodyDependencies references."""

    def test_body_dependencies_extracted(self) -> None:
        parent = Element(
            _ns("Element"),
            attrib={"Type": "SqlScalarFunction", "Name": "[dbo].[F]"},
        )
        _build_function_body(
            parent,
            "SELECT 1",
            dependencies=("[dbo].[T1]", "[dbo].[T2]"),
        )

        body_script, body_deps = extract_function_body(parent)
        assert body_script == "SELECT 1"
        assert len(body_deps) == 2
        assert body_deps[0].parts == ("dbo", "T1")
        assert body_deps[1].parts == ("dbo", "T2")


class TestExtractFunctionBodyAbsent:
    """Graceful handling when FunctionBody relationship is absent."""

    def test_missing_function_body_returns_defaults(self) -> None:
        parent = Element(
            _ns("Element"),
            attrib={"Type": "SqlScalarFunction", "Name": "[dbo].[F]"},
        )

        body_script, body_deps = extract_function_body(parent)
        assert body_script == ""
        assert body_deps == ()


class TestExtractFunctionBodyUnexpectedImplType:
    """Graceful handling when implementation element has unexpected type."""

    def test_unexpected_type_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        parent = Element(
            _ns("Element"),
            attrib={"Type": "SqlScalarFunction", "Name": "[dbo].[F]"},
        )
        _build_function_body(parent, "SELECT 1", impl_type="SqlClrFunction")

        with caplog.at_level(logging.WARNING):
            body_script, body_deps = extract_function_body(parent)
        assert body_script == ""
        assert body_deps == ()
        assert "Unexpected FunctionBody implementation type" in caplog.text
