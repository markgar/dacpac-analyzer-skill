"""Tests for SqlProcedure extractor.

Maps to Spec 08 acceptance criteria for procedure-level behavior.
"""

from __future__ import annotations

import logging
from xml.etree.ElementTree import Element, SubElement

import pytest

from constants import DAC_NAMESPACE
from parsing.extractors.procedure import SqlProcedureExtractor

_NS = DAC_NAMESPACE


def _ns(tag: str) -> str:
    """Return a namespace-qualified tag."""
    return f"{{{_NS}}}{tag}"


def _add_schema_ref(elem: Element, schema_name: str = "[Website]") -> None:
    """Add a Schema relationship to an element."""
    rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "Schema"})
    entry = SubElement(rel, _ns("Entry"))
    SubElement(entry, _ns("References"), attrib={"Name": schema_name})


def _add_parameter(
    parent: Element,
    name: str,
    type_ref_name: str = "[nvarchar]",
    *,
    is_output: str | None = None,
    type_length: str | None = None,
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
    if type_length is not None:
        SubElement(
            ts_entry,
            _ns("Property"),
            attrib={"Name": "Length", "Value": type_length},
        )


def _add_body_script(
    parent: Element,
    body_text: str,
    *,
    quoted_identifiers: str | None = None,
    ansi_nulls: str | None = None,
) -> None:
    """Add a BodyScript CDATA property to an element."""
    prop = SubElement(parent, _ns("Property"), attrib={"Name": "BodyScript"})
    attribs: dict[str, str] = {}
    if quoted_identifiers is not None:
        attribs["QuotedIdentifiers"] = quoted_identifiers
    if ansi_nulls is not None:
        attribs["AnsiNulls"] = ansi_nulls
    value = SubElement(prop, _ns("Value"), attrib=attribs)
    value.text = body_text


def _add_body_dependencies(parent: Element, *ref_names: str) -> None:
    """Add BodyDependencies relationship with References."""
    rel = SubElement(
        parent, _ns("Relationship"), attrib={"Name": "BodyDependencies"}
    )
    for ref_name in ref_names:
        entry = SubElement(rel, _ns("Entry"))
        SubElement(entry, _ns("References"), attrib={"Name": ref_name})


def _build_procedure(
    name: str = "[Website].[ActivateWebsiteLogon]",
    schema_ref: str = "[Website]",
) -> Element:
    """Build a minimal SqlProcedure element with schema reference."""
    proc = Element(_ns("Element"), attrib={"Type": "SqlProcedure", "Name": name})
    _add_schema_ref(proc, schema_ref)
    return proc


class TestProcedureWithParameters:
    """AC1: Procedure with 2 parameters — input and output."""

    def test_two_params_input_and_output(self) -> None:
        proc = _build_procedure()
        _add_parameter(
            proc,
            "[Website].[ActivateWebsiteLogon].[@LogonName]",
            "[nvarchar]",
            type_length="256",
        )
        _add_parameter(
            proc,
            "[Website].[ActivateWebsiteLogon].[@Result]",
            "[nvarchar]",
            is_output="True",
            type_length="max",
        )
        _add_body_script(proc, "SET @Result = N'OK'")

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        p = results[0]
        assert len(p.parameters) == 2
        assert p.parameters[0].is_output is False
        assert p.parameters[0].name.sub_name == "@LogonName"
        assert p.parameters[1].is_output is True
        assert p.parameters[1].name.sub_name == "@Result"
        assert p.body_script == "SET @Result = N'OK'"


class TestExecuteAsOwner:
    """AC2: Procedure with IsOwner=True → execute_as='OWNER'."""

    def test_execute_as_owner(self) -> None:
        proc = _build_procedure()
        SubElement(
            proc, _ns("Property"), attrib={"Name": "IsOwner", "Value": "True"}
        )
        SubElement(
            proc, _ns("Property"), attrib={"Name": "IsCaller", "Value": "False"}
        )

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        assert results[0].execute_as == "OWNER"


class TestExecuteAsNull:
    """AC3: Procedure with IsOwner=False, IsCaller=False → execute_as=None."""

    def test_execute_as_null(self) -> None:
        proc = _build_procedure()
        SubElement(
            proc, _ns("Property"), attrib={"Name": "IsOwner", "Value": "False"}
        )
        SubElement(
            proc, _ns("Property"), attrib={"Name": "IsCaller", "Value": "False"}
        )

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        assert results[0].execute_as is None


class TestExecuteAsCaller:
    """Procedure with IsCaller=True → execute_as='CALLER'."""

    def test_execute_as_caller(self) -> None:
        proc = _build_procedure()
        SubElement(
            proc, _ns("Property"), attrib={"Name": "IsCaller", "Value": "True"}
        )

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        assert results[0].execute_as == "CALLER"


class TestExecuteAsAbsent:
    """Procedure with no IsOwner/IsCaller properties → execute_as=None."""

    def test_execute_as_absent_defaults_none(self) -> None:
        proc = _build_procedure()

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        assert results[0].execute_as is None


class TestBodyDependencies:
    """AC6: Procedure with BodyDependencies references."""

    def test_three_body_dependencies(self) -> None:
        proc = _build_procedure("[Sales].[CalcOrder]", "[Sales]")
        _add_body_dependencies(
            proc,
            "[Sales].[Orders]",
            "[Sales].[Customers]",
            "[Sales].[GetDiscount].[@Amount]",
        )

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        deps = results[0].body_dependencies
        assert len(deps) == 3
        assert deps[0].parts == ("Sales", "Orders")
        assert deps[1].parts == ("Sales", "Customers")
        assert deps[2].parts == ("Sales", "GetDiscount", "@Amount")


class TestBodyScriptAttributes:
    """AC7: QuotedIdentifiers and AnsiNulls from Value element."""

    def test_quoted_identifiers_and_ansi_nulls_true(self) -> None:
        proc = _build_procedure()
        _add_body_script(
            proc,
            "SELECT 1",
            quoted_identifiers="True",
            ansi_nulls="True",
        )

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        assert results[0].is_ansi_nulls_on is True
        assert results[0].is_quoted_identifiers_on is True

    def test_quoted_identifiers_false(self) -> None:
        proc = _build_procedure()
        _add_body_script(
            proc,
            "SELECT 1",
            quoted_identifiers="False",
        )

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        assert results[0].is_quoted_identifiers_on is False


class TestIsAnsiNullsOnProperty:
    """IsAnsiNullsOn simple property extraction."""

    def test_explicit_false(self) -> None:
        proc = _build_procedure()
        SubElement(
            proc,
            _ns("Property"),
            attrib={"Name": "IsAnsiNullsOn", "Value": "False"},
        )

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        assert results[0].is_ansi_nulls_on is False

    def test_default_true_when_absent(self) -> None:
        proc = _build_procedure()

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        assert results[0].is_ansi_nulls_on is True


class TestMissingBodyScript:
    """Graceful handling when BodyScript is absent."""

    def test_missing_body_defaults_empty(self) -> None:
        proc = _build_procedure()

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc], None)

        assert len(results) == 1
        assert results[0].body_script == ""
        assert results[0].is_quoted_identifiers_on is True


class TestMissingNameAttribute:
    """Graceful degradation when Name attribute is absent."""

    def test_no_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        proc = Element(_ns("Element"), attrib={"Type": "SqlProcedure"})
        _add_schema_ref(proc)

        extractor = SqlProcedureExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([proc], None)
        assert results == ()
        assert "no Name attribute" in caplog.text


class TestMissingSchemaRelationship:
    """Graceful degradation when Schema relationship is absent."""

    def test_no_schema_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        proc = Element(
            _ns("Element"),
            attrib={"Type": "SqlProcedure", "Name": "[dbo].[P]"},
        )

        extractor = SqlProcedureExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([proc], None)
        assert results == ()
        assert "no Schema relationship" in caplog.text


class TestMultipleProcedures:
    """Multiple procedures extracted in one call."""

    def test_two_procedures(self) -> None:
        proc1 = _build_procedure("[dbo].[P1]", "[dbo]")
        proc2 = _build_procedure("[dbo].[P2]", "[dbo]")

        extractor = SqlProcedureExtractor()
        results = extractor.extract([proc1, proc2], None)

        assert len(results) == 2
        assert results[0].name.parts == ("dbo", "P1")
        assert results[1].name.parts == ("dbo", "P2")


class TestElementType:
    """Extractor reports correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlProcedureExtractor()
        assert extractor.element_type == "SqlProcedure"
