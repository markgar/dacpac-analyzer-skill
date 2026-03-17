"""Tests for SqlInlineTableValuedFunction extractor.

Maps to Spec 08 acceptance criteria for inline TVF behavior.
"""

from __future__ import annotations

import logging
from xml.etree.ElementTree import Element, SubElement

import pytest

from constants import DAC_NAMESPACE
from parsing.extractors.inline_tvf import (
    SqlInlineTableValuedFunctionExtractor,
)

_NS = DAC_NAMESPACE


def _ns(tag: str) -> str:
    """Return a namespace-qualified tag."""
    return f"{{{_NS}}}{tag}"


def _add_schema_ref(elem: Element, schema_name: str = "[dbo]") -> None:
    """Add a Schema relationship to an element."""
    rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "Schema"})
    entry = SubElement(rel, _ns("Entry"))
    SubElement(entry, _ns("References"), attrib={"Name": schema_name})


def _add_parameter(
    parent: Element,
    name: str,
    type_ref_name: str = "[int]",
) -> None:
    """Add a SqlSubroutineParameter to the Parameters relationship."""
    params_rel = None
    for rel in parent.findall(_ns("Relationship")):
        if rel.get("Name") == "Parameters":
            params_rel = rel
            break
    if params_rel is None:
        params_rel = SubElement(
            parent, _ns("Relationship"), attrib={"Name": "Parameters"}
        )

    entry = SubElement(params_rel, _ns("Entry"))
    param = SubElement(
        entry,
        _ns("Element"),
        attrib={"Type": "SqlSubroutineParameter", "Name": name},
    )

    ts_rel = SubElement(param, _ns("Relationship"), attrib={"Name": "Type"})
    ts_entry = SubElement(ts_rel, _ns("Entry"))
    ref_attrib = {"Name": type_ref_name, "ExternalSource": "BuiltIns"}
    SubElement(ts_entry, _ns("References"), attrib=ref_attrib)


def _add_computed_column(
    parent: Element,
    name: str,
    *,
    expression: str | None = None,
) -> None:
    """Add a SqlComputedColumn to the Columns relationship."""
    cols_rel = None
    for rel in parent.findall(_ns("Relationship")):
        if rel.get("Name") == "Columns":
            cols_rel = rel
            break
    if cols_rel is None:
        cols_rel = SubElement(
            parent, _ns("Relationship"), attrib={"Name": "Columns"}
        )

    entry = SubElement(cols_rel, _ns("Entry"))
    col = SubElement(
        entry,
        _ns("Element"),
        attrib={"Type": "SqlComputedColumn", "Name": name},
    )

    if expression is not None:
        prop = SubElement(col, _ns("Property"), attrib={"Name": "ExpressionScript"})
        value = SubElement(prop, _ns("Value"))
        value.text = expression


def _add_function_body(
    parent: Element,
    body_text: str,
    *,
    dependencies: tuple[str, ...] = (),
) -> None:
    """Add FunctionBody → SqlScriptFunctionImplementation → BodyScript."""
    rel = SubElement(parent, _ns("Relationship"), attrib={"Name": "FunctionBody"})
    entry = SubElement(rel, _ns("Entry"))
    impl = SubElement(
        entry,
        _ns("Element"),
        attrib={"Type": "SqlScriptFunctionImplementation"},
    )

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


def _build_inline_tvf(
    name: str = "[dbo].[GetItems]",
    schema_ref: str = "[dbo]",
) -> Element:
    """Build a minimal SqlInlineTableValuedFunction element."""
    func = Element(
        _ns("Element"),
        attrib={"Type": "SqlInlineTableValuedFunction", "Name": name},
    )
    _add_schema_ref(func, schema_ref)
    return func


class TestInlineTvfThreeComputedColumns:
    """AC5: Inline TVF with 3 SqlComputedColumn output columns."""

    def test_three_computed_columns(self) -> None:
        func = _build_inline_tvf()
        _add_computed_column(func, "[dbo].[GetItems].[Id]", expression="Id")
        _add_computed_column(func, "[dbo].[GetItems].[Name]", expression="Name")
        _add_computed_column(func, "[dbo].[GetItems].[Price]", expression="Price")
        _add_function_body(func, "SELECT Id, Name, Price FROM Items")

        extractor = SqlInlineTableValuedFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        tvf = results[0]
        assert len(tvf.columns) == 3
        assert all(col.is_computed is True for col in tvf.columns)
        assert tvf.columns[0].name.sub_name == "Id"
        assert tvf.columns[1].name.sub_name == "Name"
        assert tvf.columns[2].name.sub_name == "Price"


class TestInlineTvfEmptyColumns:
    """Inline TVF with no output columns."""

    def test_empty_columns(self) -> None:
        func = _build_inline_tvf()
        _add_function_body(func, "SELECT 1")

        extractor = SqlInlineTableValuedFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        assert results[0].columns == ()


class TestInlineTvfWithParameters:
    """Inline TVF with parameters."""

    def test_two_parameters(self) -> None:
        func = _build_inline_tvf()
        _add_parameter(func, "[dbo].[GetItems].[@CategoryId]", "[int]")
        _add_parameter(func, "[dbo].[GetItems].[@Active]", "[bit]")
        _add_function_body(func, "SELECT * FROM Items WHERE CategoryId = @CategoryId")

        extractor = SqlInlineTableValuedFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        assert len(results[0].parameters) == 2
        assert results[0].parameters[0].name.sub_name == "@CategoryId"
        assert results[0].parameters[1].name.sub_name == "@Active"


class TestInlineTvfNoParameters:
    """AC8: Function with no parameters extracts without error."""

    def test_empty_parameters(self) -> None:
        func = _build_inline_tvf()
        _add_function_body(func, "SELECT 1 AS Val")

        extractor = SqlInlineTableValuedFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        assert results[0].parameters == ()


class TestInlineTvfBodyAndDependencies:
    """Inline TVF with body script and dependencies."""

    def test_body_script_and_dependencies(self) -> None:
        func = _build_inline_tvf()
        _add_function_body(
            func,
            "SELECT * FROM [dbo].[Orders] o JOIN [dbo].[Items] i ON o.ItemId = i.Id",
            dependencies=("[dbo].[Orders]", "[dbo].[Items]"),
        )

        extractor = SqlInlineTableValuedFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        tvf = results[0]
        assert "Orders" in tvf.body_script
        assert len(tvf.body_dependencies) == 2
        assert tvf.body_dependencies[0].parts == ("dbo", "Orders")
        assert tvf.body_dependencies[1].parts == ("dbo", "Items")


class TestInlineTvfMissingBody:
    """Graceful handling when FunctionBody is absent."""

    def test_missing_body_defaults_empty(self) -> None:
        func = _build_inline_tvf()

        extractor = SqlInlineTableValuedFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        assert results[0].body_script == ""
        assert results[0].body_dependencies == ()


class TestInlineTvfMissingName:
    """Graceful degradation when Name attribute is absent."""

    def test_no_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        func = Element(
            _ns("Element"),
            attrib={"Type": "SqlInlineTableValuedFunction"},
        )
        _add_schema_ref(func)

        extractor = SqlInlineTableValuedFunctionExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([func], None)
        assert results == ()
        assert "no Name attribute" in caplog.text


class TestInlineTvfMissingSchema:
    """Graceful degradation when Schema relationship is absent."""

    def test_no_schema_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        func = Element(
            _ns("Element"),
            attrib={
                "Type": "SqlInlineTableValuedFunction",
                "Name": "[dbo].[F]",
            },
        )

        extractor = SqlInlineTableValuedFunctionExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([func], None)
        assert results == ()
        assert "no Schema relationship" in caplog.text


class TestInlineTvfElementType:
    """Extractor reports correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlInlineTableValuedFunctionExtractor()
        assert extractor.element_type == "SqlInlineTableValuedFunction"


class TestMultipleInlineTvfs:
    """Multiple inline TVFs extracted in one call."""

    def test_two_functions(self) -> None:
        func1 = _build_inline_tvf("[dbo].[F1]", "[dbo]")
        func2 = _build_inline_tvf("[dbo].[F2]", "[dbo]")

        extractor = SqlInlineTableValuedFunctionExtractor()
        results = extractor.extract([func1, func2], None)

        assert len(results) == 2
        assert results[0].name.parts == ("dbo", "F1")
        assert results[1].name.parts == ("dbo", "F2")
