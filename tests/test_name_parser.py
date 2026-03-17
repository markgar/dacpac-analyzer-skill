"""Tests for the bracket-quoted name parser and ParsedName model."""

import pytest

from models.parsed_name import ParsedName
from parsing.name_parser import parse_name


class TestParseNameThreePart:
    """AC 1: Three-part bracket-quoted name."""

    def test_parts(self) -> None:
        result = parse_name("[Application].[Countries].[CountryID]")
        assert result.parts == ("Application", "Countries", "CountryID")

    def test_schema_name(self) -> None:
        result = parse_name("[Application].[Countries].[CountryID]")
        assert result.schema_name == "Application"

    def test_object_name(self) -> None:
        result = parse_name("[Application].[Countries].[CountryID]")
        assert result.object_name == "Countries"

    def test_sub_name(self) -> None:
        result = parse_name("[Application].[Countries].[CountryID]")
        assert result.sub_name == "CountryID"


class TestParseNameSinglePart:
    """AC 2: Single-part bracket-quoted name."""

    def test_parts(self) -> None:
        result = parse_name("[dbo]")
        assert result.parts == ("dbo",)

    def test_schema_name_is_none(self) -> None:
        result = parse_name("[dbo]")
        assert result.schema_name is None

    def test_object_name_is_none(self) -> None:
        result = parse_name("[dbo]")
        assert result.object_name is None

    def test_sub_name_is_none(self) -> None:
        result = parse_name("[dbo]")
        assert result.sub_name is None


class TestParseNameAtPrefixParam:
    """AC 3: @-prefixed parameter name preserves the @ in the part."""

    def test_parts(self) -> None:
        result = parse_name("[Website].[CalculateCustomerPrice].[@CustomerID]")
        assert result.parts == ("Website", "CalculateCustomerPrice", "@CustomerID")

    def test_at_prefix_preserved(self) -> None:
        result = parse_name("[Website].[CalculateCustomerPrice].[@CustomerID]")
        assert result.sub_name == "@CustomerID"


class TestParseNameFourPlusParts:
    """Edge case: 4+ part extended property names."""

    def test_four_part(self) -> None:
        result = parse_name(
            "[SqlColumn].[Application].[Cities].[CityID].[Description]"
        )
        assert result.parts == (
            "SqlColumn",
            "Application",
            "Cities",
            "CityID",
            "Description",
        )

    def test_four_part_schema_and_object(self) -> None:
        result = parse_name(
            "[SqlColumn].[Application].[Cities].[CityID].[Description]"
        )
        assert result.schema_name == "SqlColumn"
        assert result.object_name == "Application"
        assert result.sub_name == "Cities"


class TestParseNameTwoPart:
    """Two-part schema-qualified name."""

    def test_parts(self) -> None:
        result = parse_name("[Application].[Countries]")
        assert result.parts == ("Application", "Countries")

    def test_schema_name(self) -> None:
        result = parse_name("[Application].[Countries]")
        assert result.schema_name == "Application"

    def test_object_name(self) -> None:
        result = parse_name("[Application].[Countries]")
        assert result.object_name == "Countries"

    def test_sub_name_is_none(self) -> None:
        result = parse_name("[Application].[Countries]")
        assert result.sub_name is None


class TestParseNameRawPreserved:
    """The raw string is stored unchanged."""

    def test_raw(self) -> None:
        raw = "[Application].[Countries].[CountryID]"
        result = parse_name(raw)
        assert result.raw == raw


class TestParseNameInvalidInput:
    """Edge case: input with no bracket-quoted parts raises ValueError."""

    def test_no_brackets(self) -> None:
        with pytest.raises(ValueError, match="No bracket-quoted parts"):
            parse_name("NoBrackets")

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError, match="No bracket-quoted parts"):
            parse_name("")


class TestParsedNameImmutability:
    """ParsedName is a frozen dataclass — mutation must be rejected."""

    def test_cannot_mutate_raw(self) -> None:
        name = parse_name("[dbo]")
        with pytest.raises(AttributeError):
            name.raw = "other"  # type: ignore[misc]

    def test_cannot_mutate_parts(self) -> None:
        name = parse_name("[dbo]")
        with pytest.raises(AttributeError):
            name.parts = ("other",)  # type: ignore[misc]

    def test_cannot_mutate_schema_name(self) -> None:
        name = parse_name("[dbo].[Foo]")
        with pytest.raises(AttributeError):
            name.schema_name = "other"  # type: ignore[misc]
