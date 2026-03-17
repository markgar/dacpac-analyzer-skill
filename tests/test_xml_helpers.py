"""Tests for XML helper functions (Spec 04 §4).

Covers acceptance criteria AC4, AC5, AC6 and edge cases.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import pytest

from constants import DAC_NAMESPACE
from parsing.xml_helpers import (
    CdataResult,
    extract_type_specifier,
    get_cdata_property,
    get_relationship_inline_elements,
    get_relationship_references,
    get_simple_property,
)

NS = DAC_NAMESPACE


def _elem(xml_str: str) -> ET.Element:
    """Parse an XML fragment with the DAC namespace as default."""
    return ET.fromstring(xml_str)


def _wrap(body: str) -> str:
    """Wrap XML body in an Element with the DAC namespace."""
    return f'<Element xmlns="{NS}" Type="Test" Name="[Test]">{body}</Element>'


class TestGetSimplePropertyAC4:
    """AC4: simple property helper returns 'False' for IsNullable."""

    def test_returns_value(self) -> None:
        xml = _wrap('<Property Name="IsNullable" Value="False" />')
        elem = _elem(xml)
        assert get_simple_property(elem, "IsNullable") == "False"

    def test_returns_none_when_missing(self) -> None:
        xml = _wrap('<Property Name="Other" Value="True" />')
        elem = _elem(xml)
        assert get_simple_property(elem, "IsNullable") is None

    def test_returns_none_on_empty_element(self) -> None:
        xml = _wrap("")
        elem = _elem(xml)
        assert get_simple_property(elem, "IsNullable") is None

    def test_multiple_properties(self) -> None:
        xml = _wrap(
            '<Property Name="A" Value="1" />'
            '<Property Name="B" Value="2" />'
        )
        elem = _elem(xml)
        assert get_simple_property(elem, "A") == "1"
        assert get_simple_property(elem, "B") == "2"

    def test_does_not_find_nested_element_properties(self) -> None:
        """Properties on inline child elements must not leak to parent."""
        xml = _wrap(
            '<Property Name="IsAnsiNullsOn" Value="True" />'
            '<Relationship Name="Columns">'
            "  <Entry>"
            '    <Element Type="SqlSimpleColumn" Name="[dbo].[T].[C]">'
            '      <Property Name="IsNullable" Value="False" />'
            "    </Element>"
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        assert get_simple_property(elem, "IsAnsiNullsOn") == "True"
        assert get_simple_property(elem, "IsNullable") is None


class TestGetCdataPropertyAC5:
    """AC5: CDATA property helper returns the full script text."""

    def test_returns_script_text(self) -> None:
        xml = _wrap(
            '<Property Name="BodyScript">'
            '<Value QuotedIdentifiers="True" AnsiNulls="True">'
            "BEGIN SET NOCOUNT ON; END;"
            "</Value>"
            "</Property>"
        )
        elem = _elem(xml)
        result = get_cdata_property(elem, "BodyScript")
        assert result is not None
        assert result.text == "BEGIN SET NOCOUNT ON; END;"
        assert result.quoted_identifiers is True
        assert result.ansi_nulls is True

    def test_returns_none_when_missing(self) -> None:
        xml = _wrap("")
        elem = _elem(xml)
        assert get_cdata_property(elem, "BodyScript") is None

    def test_empty_text(self) -> None:
        xml = _wrap(
            '<Property Name="BodyScript"><Value /></Property>'
        )
        elem = _elem(xml)
        result = get_cdata_property(elem, "BodyScript")
        assert result is not None
        assert result.text == ""

    def test_no_value_element(self) -> None:
        xml = _wrap(
            '<Property Name="BodyScript"></Property>'
        )
        elem = _elem(xml)
        assert get_cdata_property(elem, "BodyScript") is None

    def test_optional_attributes_absent(self) -> None:
        xml = _wrap(
            '<Property Name="Script">'
            "  <Value>SELECT 1</Value>"
            "</Property>"
        )
        elem = _elem(xml)
        result = get_cdata_property(elem, "Script")
        assert result is not None
        assert result.text == "SELECT 1"
        assert result.quoted_identifiers is None
        assert result.ansi_nulls is None


class TestGetRelationshipReferences:
    """Test relationship reference extraction."""

    def test_single_reference(self) -> None:
        xml = _wrap(
            '<Relationship Name="Schema">'
            "  <Entry>"
            '    <References Name="[dbo]" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        refs = get_relationship_references(elem, "Schema")
        assert len(refs) == 1
        assert refs[0].raw == "[dbo]"

    def test_multiple_references(self) -> None:
        xml = _wrap(
            '<Relationship Name="Columns">'
            "  <Entry>"
            '    <References Name="[dbo].[T].[A]" />'
            "  </Entry>"
            "  <Entry>"
            '    <References Name="[dbo].[T].[B]" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        refs = get_relationship_references(elem, "Columns")
        assert len(refs) == 2
        assert refs[0].parts == ("dbo", "T", "A")
        assert refs[1].parts == ("dbo", "T", "B")

    def test_missing_relationship(self) -> None:
        xml = _wrap("")
        elem = _elem(xml)
        refs = get_relationship_references(elem, "Schema")
        assert refs == ()

    def test_exclude_builtins(self) -> None:
        xml = _wrap(
            '<Relationship Name="TypeSpecifier">'
            "  <Entry>"
            '    <References Name="[int]" ExternalSource="BuiltIns" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        refs_all = get_relationship_references(elem, "TypeSpecifier")
        assert len(refs_all) == 1
        refs_filtered = get_relationship_references(
            elem, "TypeSpecifier", exclude_builtins=True
        )
        assert len(refs_filtered) == 0

    def test_malformed_name_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        xml = _wrap(
            '<Relationship Name="Schema">'
            "  <Entry>"
            '    <References Name="no-brackets" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        with caplog.at_level(logging.WARNING):
            refs = get_relationship_references(elem, "Schema")
        assert refs == ()
        assert "malformed" in caplog.text.lower()

    def test_does_not_find_nested_element_relationships(self) -> None:
        """Relationships on inline child elements must not leak to parent."""
        xml = _wrap(
            '<Relationship Name="Schema">'
            "  <Entry>"
            '    <References Name="[dbo]" />'
            "  </Entry>"
            "</Relationship>"
            '<Relationship Name="Columns">'
            "  <Entry>"
            '    <Element Type="SqlSimpleColumn" Name="[dbo].[T].[C]">'
            '      <Relationship Name="TypeSpecifier">'
            "        <Entry>"
            '          <References Name="[int]" ExternalSource="BuiltIns" />'
            "        </Entry>"
            "      </Relationship>"
            "    </Element>"
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        # Parent should see Schema but not the nested TypeSpecifier
        schema_refs = get_relationship_references(elem, "Schema")
        assert len(schema_refs) == 1
        type_refs = get_relationship_references(elem, "TypeSpecifier")
        assert len(type_refs) == 0


class TestGetRelationshipInlineElements:
    """Test inline element extraction from relationships."""

    def test_inline_elements(self) -> None:
        xml = _wrap(
            '<Relationship Name="Columns">'
            "  <Entry>"
            f'    <Element Type="SqlSimpleColumn" Name="[dbo].[T].[C]" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        inlines = get_relationship_inline_elements(elem, "Columns")
        assert len(inlines) == 1
        assert inlines[0].get("Type") == "SqlSimpleColumn"

    def test_missing_relationship(self) -> None:
        xml = _wrap("")
        elem = _elem(xml)
        inlines = get_relationship_inline_elements(elem, "Columns")
        assert inlines == ()

    def test_multiple_entries(self) -> None:
        xml = _wrap(
            '<Relationship Name="Columns">'
            "  <Entry>"
            f'    <Element Type="SqlSimpleColumn" Name="[dbo].[T].[A]" />'
            "  </Entry>"
            "  <Entry>"
            f'    <Element Type="SqlComputedColumn" Name="[dbo].[T].[B]" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        inlines = get_relationship_inline_elements(elem, "Columns")
        assert len(inlines) == 2


class TestExtractTypeSpecifierAC6:
    """AC6: TypeSpecifier extraction returns correct model."""

    def test_nvarchar_60_builtin(self) -> None:
        xml = _wrap(
            '<Relationship Name="TypeSpecifier">'
            "  <Entry>"
            '    <References Name="[nvarchar]" ExternalSource="BuiltIns" />'
            '    <Property Name="Length" Value="60" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        ts = extract_type_specifier(elem)
        assert ts is not None
        assert ts.type_name == "nvarchar"
        assert ts.length == 60
        assert ts.is_builtin is True
        assert ts.precision is None
        assert ts.scale is None
        assert ts.is_max is False

    def test_no_type_specifier_returns_none(self) -> None:
        xml = _wrap("")
        elem = _elem(xml)
        assert extract_type_specifier(elem) is None

    def test_decimal_with_precision_scale(self) -> None:
        xml = _wrap(
            '<Relationship Name="TypeSpecifier">'
            "  <Entry>"
            '    <References Name="[decimal]" ExternalSource="BuiltIns" />'
            '    <Property Name="Precision" Value="18" />'
            '    <Property Name="Scale" Value="4" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        ts = extract_type_specifier(elem)
        assert ts is not None
        assert ts.type_name == "decimal"
        assert ts.precision == 18
        assert ts.scale == 4
        assert ts.is_builtin is True

    def test_varchar_max(self) -> None:
        xml = _wrap(
            '<Relationship Name="TypeSpecifier">'
            "  <Entry>"
            '    <References Name="[varchar]" ExternalSource="BuiltIns" />'
            '    <Property Name="IsMax" Value="True" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        ts = extract_type_specifier(elem)
        assert ts is not None
        assert ts.type_name == "varchar"
        assert ts.is_max is True
        assert ts.length is None

    def test_non_builtin_type(self) -> None:
        xml = _wrap(
            '<Relationship Name="TypeSpecifier">'
            "  <Entry>"
            '    <References Name="[dbo].[MyType]" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        ts = extract_type_specifier(elem)
        assert ts is not None
        assert ts.type_name == "MyType"
        assert ts.is_builtin is False

    def test_malformed_length_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        xml = _wrap(
            '<Relationship Name="TypeSpecifier">'
            "  <Entry>"
            '    <References Name="[int]" ExternalSource="BuiltIns" />'
            '    <Property Name="Length" Value="abc" />'
            "  </Entry>"
            "</Relationship>"
        )
        elem = _elem(xml)
        with caplog.at_level(logging.WARNING):
            ts = extract_type_specifier(elem)
        assert ts is not None
        assert ts.length is None
        assert "malformed" in caplog.text.lower()


class TestExtractTypeSpecifierInlinePattern:
    """Inline SqlTypeSpecifier pattern used by real-world dacpac/bacpac files.

    Real packages wrap type info in an inner Element::

        <Relationship Name="TypeSpecifier">
          <Entry>
            <Element Type="SqlTypeSpecifier">
              <Relationship Name="Type">
                <Entry>
                  <References Name="[nvarchar]" ExternalSource="BuiltIns" />
                </Entry>
              </Relationship>
              <Property Name="Length" Value="60" />
            </Element>
          </Entry>
        </Relationship>

    Facets (Length, Precision, Scale, IsMax) live on the SqlTypeSpecifier
    Element, not on the outer Entry.
    """

    @staticmethod
    def _inline_xml(
        type_name: str,
        *,
        external_source: str | None = "BuiltIns",
        facets: str = "",
        relationship_name: str = "TypeSpecifier",
    ) -> str:
        ext = f' ExternalSource="{external_source}"' if external_source else ""
        return _wrap(
            f'<Relationship Name="{relationship_name}">'
            "  <Entry>"
            '    <Element Type="SqlTypeSpecifier">'
            '      <Relationship Name="Type">'
            "        <Entry>"
            f'          <References Name="{type_name}"{ext} />'
            "        </Entry>"
            "      </Relationship>"
            f"      {facets}"
            "    </Element>"
            "  </Entry>"
            "</Relationship>"
        )

    def test_nvarchar_with_length(self) -> None:
        xml = self._inline_xml(
            "[nvarchar]", facets='<Property Name="Length" Value="60" />'
        )
        ts = extract_type_specifier(_elem(xml))
        assert ts is not None
        assert ts.type_name == "nvarchar"
        assert ts.length == 60
        assert ts.is_builtin is True
        assert ts.precision is None
        assert ts.scale is None
        assert ts.is_max is False

    def test_decimal_with_precision_and_scale(self) -> None:
        xml = self._inline_xml(
            "[decimal]",
            facets=(
                '<Property Name="Precision" Value="18" />'
                '<Property Name="Scale" Value="2" />'
            ),
        )
        ts = extract_type_specifier(_elem(xml))
        assert ts is not None
        assert ts.type_name == "decimal"
        assert ts.precision == 18
        assert ts.scale == 2
        assert ts.length is None

    def test_varchar_max(self) -> None:
        xml = self._inline_xml(
            "[varchar]", facets='<Property Name="IsMax" Value="True" />'
        )
        ts = extract_type_specifier(_elem(xml))
        assert ts is not None
        assert ts.type_name == "varchar"
        assert ts.is_max is True
        assert ts.length is None

    def test_int_no_facets(self) -> None:
        xml = self._inline_xml("[int]")
        ts = extract_type_specifier(_elem(xml))
        assert ts is not None
        assert ts.type_name == "int"
        assert ts.is_builtin is True
        assert ts.length is None
        assert ts.precision is None
        assert ts.scale is None
        assert ts.is_max is False

    def test_non_builtin_type(self) -> None:
        xml = self._inline_xml("[dbo].[MyUDT]", external_source=None)
        ts = extract_type_specifier(_elem(xml))
        assert ts is not None
        assert ts.type_name == "MyUDT"
        assert ts.is_builtin is False

    def test_custom_relationship_name(self) -> None:
        """SqlSubroutineParameter uses 'Type' instead of 'TypeSpecifier'."""
        xml = self._inline_xml(
            "[nvarchar]",
            relationship_name="Type",
            facets='<Property Name="Length" Value="100" />',
        )
        ts = extract_type_specifier(_elem(xml), relationship_name="Type")
        assert ts is not None
        assert ts.type_name == "nvarchar"
        assert ts.length == 100

    def test_malformed_length_on_inline_element(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        xml = self._inline_xml(
            "[int]", facets='<Property Name="Length" Value="bad" />'
        )
        with caplog.at_level(logging.WARNING):
            ts = extract_type_specifier(_elem(xml))
        assert ts is not None
        assert ts.length is None
        assert "malformed" in caplog.text.lower()

    def test_direct_pattern_preferred_over_inline(self) -> None:
        """When Entry has a direct References, inline is not checked."""
        xml = _wrap(
            '<Relationship Name="TypeSpecifier">'
            "  <Entry>"
            '    <References Name="[bigint]" ExternalSource="BuiltIns" />'
            '    <Element Type="SqlTypeSpecifier">'
            '      <Relationship Name="Type">'
            "        <Entry>"
            '          <References Name="[int]" ExternalSource="BuiltIns" />'
            "        </Entry>"
            "      </Relationship>"
            "    </Element>"
            "  </Entry>"
            "</Relationship>"
        )
        ts = extract_type_specifier(_elem(xml))
        assert ts is not None
        assert ts.type_name == "bigint"


class TestCdataResultImmutability:
    """CdataResult is a frozen dataclass."""

    def test_frozen(self) -> None:
        result = CdataResult(text="test")
        with pytest.raises(AttributeError):
            result.text = "changed"  # type: ignore[misc]
