"""Tests for constants and enumeration types."""

from constants import (
    BUILTIN_EXTERNAL_SOURCE,
    CONTENT_TYPES_XML,
    DAC_METADATA_XML,
    DAC_NAMESPACE,
    MODEL_XML,
    ORIGIN_XML,
)
from models.enums import (
    CompressionLevel,
    Durability,
    ElementType,
    PartitionRange,
    SortOrder,
)


class TestConstants:
    def test_dac_namespace(self) -> None:
        assert DAC_NAMESPACE == "http://schemas.microsoft.com/sqlserver/dac/Serialization/2012/02"

    def test_file_names(self) -> None:
        assert MODEL_XML == "model.xml"
        assert DAC_METADATA_XML == "DacMetadata.xml"
        assert ORIGIN_XML == "Origin.xml"
        assert CONTENT_TYPES_XML == "[Content_Types].xml"

    def test_builtin_external_source(self) -> None:
        assert BUILTIN_EXTERNAL_SOURCE == "BuiltIns"


class TestElementType:
    """AC 4: ElementType resolution from model.xml Type strings."""

    def test_resolve_known_type_sql_table(self) -> None:
        result = ElementType.from_type_string("SqlTable")
        assert result is ElementType.TABLE

    def test_resolve_known_type_sql_view(self) -> None:
        result = ElementType.from_type_string("SqlView")
        assert result is ElementType.VIEW

    def test_resolve_known_type_sql_procedure(self) -> None:
        result = ElementType.from_type_string("SqlProcedure")
        assert result is ElementType.PROCEDURE

    def test_resolve_known_type_sql_schema(self) -> None:
        result = ElementType.from_type_string("SqlSchema")
        assert result is ElementType.SCHEMA

    def test_resolve_known_type_sql_primary_key(self) -> None:
        result = ElementType.from_type_string("SqlPrimaryKeyConstraint")
        assert result is ElementType.PRIMARY_KEY

    def test_resolve_unknown_type_returns_unknown(self) -> None:
        result = ElementType.from_type_string("UnknownFutureType")
        assert result is ElementType.UNKNOWN

    def test_resolve_empty_string_returns_unknown(self) -> None:
        result = ElementType.from_type_string("")
        assert result is ElementType.UNKNOWN

    def test_all_known_types_have_unique_values(self) -> None:
        values = [m.value for m in ElementType if m is not ElementType.UNKNOWN]
        assert len(values) == len(set(values))

    def test_has_26_known_members_plus_unknown(self) -> None:
        assert len(ElementType) == 27

    def test_every_known_member_round_trips(self) -> None:
        for member in ElementType:
            if member is ElementType.UNKNOWN:
                continue
            assert ElementType.from_type_string(member.value) is member


class TestSortOrder:
    def test_ascending(self) -> None:
        assert SortOrder.ASCENDING.value == "Ascending"

    def test_descending(self) -> None:
        assert SortOrder.DESCENDING.value == "Descending"


class TestCompressionLevel:
    def test_values(self) -> None:
        assert CompressionLevel.NONE == 0
        assert CompressionLevel.ROW == 1
        assert CompressionLevel.PAGE == 2


class TestPartitionRange:
    def test_values(self) -> None:
        assert PartitionRange.LEFT == 1
        assert PartitionRange.RIGHT == 2


class TestDurability:
    def test_values(self) -> None:
        assert Durability.SCHEMA_AND_DATA == 0
        assert Durability.SCHEMA_ONLY == 1
