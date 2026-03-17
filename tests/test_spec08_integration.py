"""Integration tests for Spec 08 programmable object extractors.

Verifies that all three extractors (SqlProcedure, SqlScalarFunction,
SqlInlineTableValuedFunction) work together via the registry and
dispatch mechanism.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement

from constants import DAC_NAMESPACE
from parsing.extractors import register_spec08_extractors
from parsing.registry import ExtractorRegistry

_NS = DAC_NAMESPACE


def _ns(tag: str) -> str:
    """Return a namespace-qualified tag."""
    return f"{{{_NS}}}{tag}"


def _add_schema_ref(elem: Element, schema_name: str = "[dbo]") -> None:
    """Add a Schema relationship to an element."""
    rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "Schema"})
    entry = SubElement(rel, _ns("Entry"))
    SubElement(entry, _ns("References"), attrib={"Name": schema_name})


def _add_return_type(elem: Element, type_ref_name: str = "[int]") -> None:
    """Add a Type relationship to a function element."""
    rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "Type"})
    entry = SubElement(rel, _ns("Entry"))
    SubElement(
        entry,
        _ns("References"),
        attrib={"Name": type_ref_name, "ExternalSource": "BuiltIns"},
    )


class TestSpec08Registration:
    """All spec 08 extractors are registered correctly."""

    def test_three_extractors_registered(self) -> None:
        registry = ExtractorRegistry()
        register_spec08_extractors(registry)

        assert len(registry) == 3
        assert "SqlProcedure" in registry
        assert "SqlScalarFunction" in registry
        assert "SqlInlineTableValuedFunction" in registry

    def test_no_duplicate_with_repeated_registration(self) -> None:
        """Verifying idempotency check — duplicate raises ValueError."""
        registry = ExtractorRegistry()
        register_spec08_extractors(registry)

        import pytest

        with pytest.raises(ValueError, match="Duplicate"):
            register_spec08_extractors(registry)


class TestSpec08ExtractorsViaRegistry:
    """Extractors retrieved from registry produce correct domain models."""

    def test_procedure_via_registry(self) -> None:
        registry = ExtractorRegistry()
        register_spec08_extractors(registry)

        proc = Element(
            _ns("Element"),
            attrib={"Type": "SqlProcedure", "Name": "[dbo].[MyProc]"},
        )
        _add_schema_ref(proc)

        extractor = registry.get("SqlProcedure")
        assert extractor is not None
        results = extractor.extract([proc], None)
        assert len(results) == 1
        assert results[0].name.parts == ("dbo", "MyProc")

    def test_scalar_function_via_registry(self) -> None:
        registry = ExtractorRegistry()
        register_spec08_extractors(registry)

        func = Element(
            _ns("Element"),
            attrib={"Type": "SqlScalarFunction", "Name": "[dbo].[MyFunc]"},
        )
        _add_schema_ref(func)
        _add_return_type(func)

        extractor = registry.get("SqlScalarFunction")
        assert extractor is not None
        results = extractor.extract([func], None)
        assert len(results) == 1
        assert results[0].name.parts == ("dbo", "MyFunc")

    def test_inline_tvf_via_registry(self) -> None:
        registry = ExtractorRegistry()
        register_spec08_extractors(registry)

        func = Element(
            _ns("Element"),
            attrib={
                "Type": "SqlInlineTableValuedFunction",
                "Name": "[dbo].[MyTvf]",
            },
        )
        _add_schema_ref(func)

        extractor = registry.get("SqlInlineTableValuedFunction")
        assert extractor is not None
        results = extractor.extract([func], None)
        assert len(results) == 1
        assert results[0].name.parts == ("dbo", "MyTvf")
