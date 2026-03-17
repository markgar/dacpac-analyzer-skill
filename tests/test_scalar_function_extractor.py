"""Tests for SqlScalarFunction extractor.

Maps to Spec 08 acceptance criteria for scalar function behavior.
"""

from __future__ import annotations

import logging
from xml.etree.ElementTree import Element, SubElement

import pytest

from constants import DAC_NAMESPACE
from parsing.extractors.scalar_function import SqlScalarFunctionExtractor

_NS = DAC_NAMESPACE


def _ns(tag: str) -> str:
    """Return a namespace-qualified tag."""
    return f"{{{_NS}}}{tag}"


def _add_schema_ref(elem: Element, schema_name: str = "[dbo]") -> None:
    """Add a Schema relationship to an element."""
    rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "Schema"})
    entry = SubElement(rel, _ns("Entry"))
    SubElement(entry, _ns("References"), attrib={"Name": schema_name})


def _add_return_type(
    elem: Element,
    type_ref_name: str = "[int]",
    *,
    is_builtin: bool = True,
    length: str | None = None,
) -> None:
    """Add a Type relationship (return type) to a function element."""
    rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "Type"})
    entry = SubElement(rel, _ns("Entry"))
    ref_attrib = {"Name": type_ref_name}
    if is_builtin:
        ref_attrib["ExternalSource"] = "BuiltIns"
    SubElement(entry, _ns("References"), attrib=ref_attrib)
    if length is not None:
        SubElement(
            entry, _ns("Property"), attrib={"Name": "Length", "Value": length}
        )


def _add_parameter(
    parent: Element,
    name: str,
    type_ref_name: str = "[int]",
    *,
    is_output: str | None = None,
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

    if is_output is not None:
        SubElement(
            param, _ns("Property"), attrib={"Name": "IsOutput", "Value": is_output}
        )

    ts_rel = SubElement(param, _ns("Relationship"), attrib={"Name": "Type"})
    ts_entry = SubElement(ts_rel, _ns("Entry"))
    ref_attrib = {"Name": type_ref_name, "ExternalSource": "BuiltIns"}
    SubElement(ts_entry, _ns("References"), attrib=ref_attrib)


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


def _build_scalar_function(
    name: str = "[dbo].[GetTotal]",
    schema_ref: str = "[dbo]",
    return_type: str = "[int]",
) -> Element:
    """Build a minimal SqlScalarFunction element."""
    func = Element(
        _ns("Element"),
        attrib={"Type": "SqlScalarFunction", "Name": name},
    )
    _add_schema_ref(func, schema_ref)
    _add_return_type(func, return_type)
    return func


class TestScalarFunctionBodyAndReturnType:
    """AC4: Scalar function with body containing 'RETURN @result' and return type populated."""

    def test_body_script_and_return_type(self) -> None:
        func = _build_scalar_function()
        _add_function_body(func, "RETURN @result")

        extractor = SqlScalarFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        sf = results[0]
        assert sf.body_script == "RETURN @result"
        assert sf.return_type.type_name == "int"
        assert sf.return_type.is_builtin is True


class TestScalarFunctionNoParameters:
    """AC8: Function with no parameters extracts without error."""

    def test_empty_parameters(self) -> None:
        func = _build_scalar_function()
        _add_function_body(func, "RETURN 42")

        extractor = SqlScalarFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        assert results[0].parameters == ()


class TestScalarFunctionWithParameters:
    """Scalar function with parameters."""

    def test_two_parameters(self) -> None:
        func = _build_scalar_function()
        _add_parameter(func, "[dbo].[GetTotal].[@Amount]", "[decimal]")
        _add_parameter(func, "[dbo].[GetTotal].[@Rate]", "[float]")
        _add_function_body(func, "RETURN @Amount * @Rate")

        extractor = SqlScalarFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        sf = results[0]
        assert len(sf.parameters) == 2
        assert sf.parameters[0].name.sub_name == "@Amount"
        assert sf.parameters[1].name.sub_name == "@Rate"


class TestScalarFunctionBodyDependencies:
    """Scalar function with body dependencies."""

    def test_dependencies_from_function_body(self) -> None:
        func = _build_scalar_function()
        _add_function_body(
            func,
            "RETURN (SELECT TOP 1 Val FROM [dbo].[Config])",
            dependencies=("[dbo].[Config]",),
        )

        extractor = SqlScalarFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        assert len(results[0].body_dependencies) == 1
        assert results[0].body_dependencies[0].parts == ("dbo", "Config")


class TestScalarFunctionMissingBody:
    """Graceful handling when FunctionBody is absent."""

    def test_missing_body_defaults_empty(self) -> None:
        func = _build_scalar_function()

        extractor = SqlScalarFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        assert results[0].body_script == ""
        assert results[0].body_dependencies == ()


class TestScalarFunctionMissingName:
    """Graceful degradation when Name attribute is absent."""

    def test_no_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        func = Element(
            _ns("Element"), attrib={"Type": "SqlScalarFunction"}
        )
        _add_schema_ref(func)
        _add_return_type(func)

        extractor = SqlScalarFunctionExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([func], None)
        assert results == ()
        assert "no Name attribute" in caplog.text


class TestScalarFunctionMissingSchema:
    """Graceful degradation when Schema relationship is absent."""

    def test_no_schema_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        func = Element(
            _ns("Element"),
            attrib={"Type": "SqlScalarFunction", "Name": "[dbo].[F]"},
        )
        _add_return_type(func)

        extractor = SqlScalarFunctionExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([func], None)
        assert results == ()
        assert "no Schema relationship" in caplog.text


class TestScalarFunctionMissingReturnType:
    """Graceful degradation when Type relationship is absent."""

    def test_no_return_type_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        func = Element(
            _ns("Element"),
            attrib={"Type": "SqlScalarFunction", "Name": "[dbo].[F]"},
        )
        _add_schema_ref(func)

        extractor = SqlScalarFunctionExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([func], None)
        assert results == ()
        assert "no return type" in caplog.text


class TestScalarFunctionReturnTypeWithFacets:
    """Return type with length/precision facets."""

    def test_return_type_with_length(self) -> None:
        func = Element(
            _ns("Element"),
            attrib={"Type": "SqlScalarFunction", "Name": "[dbo].[F]"},
        )
        _add_schema_ref(func)
        _add_return_type(func, "[nvarchar]", length="100")
        _add_function_body(func, "RETURN N'hello'")

        extractor = SqlScalarFunctionExtractor()
        results = extractor.extract([func], None)

        assert len(results) == 1
        assert results[0].return_type.type_name == "nvarchar"
        assert results[0].return_type.length == 100


class TestScalarFunctionElementType:
    """Extractor reports correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlScalarFunctionExtractor()
        assert extractor.element_type == "SqlScalarFunction"


class TestMultipleScalarFunctions:
    """Multiple functions extracted in one call."""

    def test_two_functions(self) -> None:
        func1 = _build_scalar_function("[dbo].[F1]", "[dbo]", "[int]")
        func2 = _build_scalar_function("[dbo].[F2]", "[dbo]", "[bit]")

        extractor = SqlScalarFunctionExtractor()
        results = extractor.extract([func1, func2], None)

        assert len(results) == 2
        assert results[0].name.parts == ("dbo", "F1")
        assert results[1].name.parts == ("dbo", "F2")
