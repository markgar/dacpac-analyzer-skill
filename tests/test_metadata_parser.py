"""Tests for XmlMetadataParser — DacMetadata.xml and Origin.xml parsing.

Covers acceptance criteria AC1–AC7 from Spec 03 plus edge cases.
"""

from __future__ import annotations

import logging

import pytest

from constants import DAC_NAMESPACE
from parsing.metadata_parser import XmlMetadataParser

NS = DAC_NAMESPACE


def _dac_metadata_xml(name: str, version: str) -> bytes:
    """Build a minimal DacMetadata.xml."""
    return (
        f'<DacType xmlns="{NS}">'
        f"<Name>{name}</Name>"
        f"<Version>{version}</Version>"
        f"</DacType>"
    ).encode("utf-8")


def _origin_xml(body: str) -> bytes:
    """Wrap Origin.xml body in a namespace-qualified DacOrigin root."""
    return f'<DacOrigin xmlns="{NS}">{body}</DacOrigin>'.encode("utf-8")


# ---------------------------------------------------------------------------
# DacMetadata.xml — AC1 and edge cases
# ---------------------------------------------------------------------------


class TestParseMetadataAC1:
    """AC1: GIVEN DacMetadata.xml with Name and Version WHEN parsed THEN fields match."""

    def test_name_and_version(self) -> None:
        xml = _dac_metadata_xml("WideWorldImporters", "1.0.0.0")
        result = XmlMetadataParser().parse_metadata(xml)
        assert result.name == "WideWorldImporters"
        assert result.version == "1.0.0.0"


class TestParseMetadataMissingName:
    """Edge case: missing Name element raises ValueError."""

    def test_missing_name_raises(self) -> None:
        xml = f'<DacType xmlns="{NS}"><Version>1.0.0.0</Version></DacType>'.encode()
        with pytest.raises(ValueError, match="<Name>"):
            XmlMetadataParser().parse_metadata(xml)


class TestParseMetadataMissingVersion:
    """Edge case: missing Version element raises ValueError."""

    def test_missing_version_raises(self) -> None:
        xml = f'<DacType xmlns="{NS}"><Name>Test</Name></DacType>'.encode()
        with pytest.raises(ValueError, match="<Version>"):
            XmlMetadataParser().parse_metadata(xml)


# ---------------------------------------------------------------------------
# Origin.xml — AC2–AC7 and edge cases
# ---------------------------------------------------------------------------


class TestParseOriginAC2:
    """AC2: ContainsExportedData=true → True."""

    def test_contains_exported_data_true(self) -> None:
        xml = _origin_xml(
            "<PackageProperties>"
            "<ContainsExportedData>true</ContainsExportedData>"
            "</PackageProperties>"
        )
        result = XmlMetadataParser().parse_origin(xml)
        assert result.contains_exported_data is True


class TestParseOriginAC3:
    """AC3: ContainsExportedData=false → False."""

    def test_contains_exported_data_false(self) -> None:
        xml = _origin_xml(
            "<PackageProperties>"
            "<ContainsExportedData>false</ContainsExportedData>"
            "</PackageProperties>"
        )
        result = XmlMetadataParser().parse_origin(xml)
        assert result.contains_exported_data is False


class TestParseOriginAC4:
    """AC4: ObjectCounts with Table=48 and View=3."""

    def test_object_counts(self) -> None:
        xml = _origin_xml(
            "<ObjectCounts>"
            "<Table>48</Table>"
            "<View>3</View>"
            "</ObjectCounts>"
        )
        result = XmlMetadataParser().parse_origin(xml)
        assert result.object_counts == {"Table": 48, "View": 3}


class TestParseOriginAC5:
    """AC5: Missing ExportStatistics → size and row count are None."""

    def test_missing_export_statistics(self) -> None:
        xml = _origin_xml("")
        result = XmlMetadataParser().parse_origin(xml)
        assert result.source_database_size_kb is None
        assert result.total_row_count is None


class TestParseOriginAC6:
    """AC6: Checksum with Uri=/model.xml → model_checksum extracted."""

    def test_model_checksum(self) -> None:
        xml = _origin_xml(
            "<Checksums>"
            '<Checksum Uri="/model.xml">abc123</Checksum>'
            "</Checksums>"
        )
        result = XmlMetadataParser().parse_origin(xml)
        assert result.model_checksum == "abc123"


class TestParseOriginAC7:
    """AC7: Missing Checksums → model_checksum is None."""

    def test_missing_checksums(self) -> None:
        xml = _origin_xml("")
        result = XmlMetadataParser().parse_origin(xml)
        assert result.model_checksum is None


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


class TestParseOriginEmptyObjectCounts:
    """Edge case: empty ObjectCounts element → empty dict."""

    def test_empty_object_counts(self) -> None:
        xml = _origin_xml("<ObjectCounts></ObjectCounts>")
        result = XmlMetadataParser().parse_origin(xml)
        assert result.object_counts == {}


class TestParseOriginMissingObjectCounts:
    """Edge case: ObjectCounts element absent → empty dict."""

    def test_missing_object_counts(self) -> None:
        xml = _origin_xml("")
        result = XmlMetadataParser().parse_origin(xml)
        assert result.object_counts == {}


class TestParseOriginUnexpectedCountTags:
    """Edge case: unexpected child tags under ObjectCounts are included."""

    def test_unexpected_tags_included(self) -> None:
        xml = _origin_xml(
            "<ObjectCounts>"
            "<Table>10</Table>"
            "<CustomThing>5</CustomThing>"
            "</ObjectCounts>"
        )
        result = XmlMetadataParser().parse_origin(xml)
        assert result.object_counts == {"Table": 10, "CustomThing": 5}


class TestParseOriginOperationFields:
    """Edge case: Operation section parsed for export_timestamp and product_version."""

    def test_operation_fields(self) -> None:
        xml = _origin_xml(
            "<Operation>"
            "<Start>2024-01-15T10:30:00Z</Start>"
            "<ProductVersion>162.1.111.0</ProductVersion>"
            "</Operation>"
        )
        result = XmlMetadataParser().parse_origin(xml)
        assert result.export_timestamp == "2024-01-15T10:30:00Z"
        assert result.product_version == "162.1.111.0"


class TestParseOriginServerVersion:
    """Edge case: Server section parsed for server_version."""

    def test_server_version(self) -> None:
        xml = _origin_xml(
            "<Server>"
            "<ServerVersion>16.00.1135</ServerVersion>"
            "</Server>"
        )
        result = XmlMetadataParser().parse_origin(xml)
        assert result.server_version == "16.00.1135"


class TestParseOriginExportStatistics:
    """Edge case: ExportStatistics section parsed correctly."""

    def test_export_statistics(self) -> None:
        xml = _origin_xml(
            "<ExportStatistics>"
            "<SourceDatabaseSize>102400</SourceDatabaseSize>"
            "<TableRowCountTotalTag>50000</TableRowCountTotalTag>"
            "</ExportStatistics>"
        )
        result = XmlMetadataParser().parse_origin(xml)
        assert result.source_database_size_kb == 102400
        assert result.total_row_count == 50000


class TestParseOriginModelSchemaVersion:
    """Edge case: ModelSchemaVersion parsed when present."""

    def test_model_schema_version(self) -> None:
        xml = _origin_xml("<ModelSchemaVersion>2.9</ModelSchemaVersion>")
        result = XmlMetadataParser().parse_origin(xml)
        assert result.model_schema_version == "2.9"


class TestParseOriginChecksumWithMultipleEntries:
    """Edge case: only the /model.xml checksum is picked from multiple."""

    def test_multiple_checksums(self) -> None:
        xml = _origin_xml(
            "<Checksums>"
            '<Checksum Uri="/other.xml">ignored</Checksum>'
            '<Checksum Uri="/model.xml">correct_hash</Checksum>'
            "</Checksums>"
        )
        result = XmlMetadataParser().parse_origin(xml)
        assert result.model_checksum == "correct_hash"


class TestParseOriginAllFieldsNoneWhenEmpty:
    """Edge case: empty Origin.xml → all optional fields None, counts empty."""

    def test_all_optional_fields_none(self) -> None:
        xml = _origin_xml("")
        result = XmlMetadataParser().parse_origin(xml)
        assert result.contains_exported_data is False
        assert result.server_version is None
        assert result.product_version is None
        assert result.object_counts == {}
        assert result.source_database_size_kb is None
        assert result.total_row_count is None
        assert result.model_checksum is None
        assert result.model_schema_version is None
        assert result.export_timestamp is None


# ---------------------------------------------------------------------------
# Full-document integration tests (Task 3)
# ---------------------------------------------------------------------------

# Realistic complete DacMetadata.xml with XML declaration and all elements
_FULL_DAC_METADATA_XML: bytes = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    f'<DacType xmlns="{NS}">\n'
    "  <Name>WideWorldImporters</Name>\n"
    "  <Version>1.0.0.0</Version>\n"
    "</DacType>"
).encode("utf-8")

# Realistic complete Origin.xml with all sections populated
_FULL_ORIGIN_XML: bytes = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    f'<DacOrigin xmlns="{NS}">\n'
    "  <PackageProperties>\n"
    "    <ContainsExportedData>true</ContainsExportedData>\n"
    "  </PackageProperties>\n"
    "  <Operation>\n"
    "    <Start>2025-06-15T09:22:47.1234567+00:00</Start>\n"
    "    <ProductVersion>162.1.167.1</ProductVersion>\n"
    "  </Operation>\n"
    "  <Server>\n"
    "    <ServerVersion>16.00.4165</ServerVersion>\n"
    "  </Server>\n"
    "  <ObjectCounts>\n"
    "    <Table>48</Table>\n"
    "    <View>3</View>\n"
    "    <Procedure>42</Procedure>\n"
    "    <SimpleColumn>636</SimpleColumn>\n"
    "    <ScalarFunction>7</ScalarFunction>\n"
    "    <Schema>5</Schema>\n"
    "    <Sequence>2</Sequence>\n"
    "    <Index>19</Index>\n"
    "  </ObjectCounts>\n"
    "  <ExportStatistics>\n"
    "    <SourceDatabaseSize>131072</SourceDatabaseSize>\n"
    "    <TableRowCountTotalTag>250000</TableRowCountTotalTag>\n"
    "  </ExportStatistics>\n"
    "  <Checksums>\n"
    '    <Checksum Uri="/predeploy.sql">aaa111</Checksum>\n'
    '    <Checksum Uri="/model.xml">e3b0c44298fc1c149afbf4c8996fb924</Checksum>\n'
    '    <Checksum Uri="/postdeploy.sql">bbb222</Checksum>\n'
    "  </Checksums>\n"
    "  <ModelSchemaVersion>2.9</ModelSchemaVersion>\n"
    "</DacOrigin>"
).encode("utf-8")


class TestFullDocumentIntegrationMetadata:
    """Integration: parse a complete realistic DacMetadata.xml and validate all fields."""

    def test_full_dac_metadata(self) -> None:
        result = XmlMetadataParser().parse_metadata(_FULL_DAC_METADATA_XML)

        assert result.name == "WideWorldImporters"
        assert result.version == "1.0.0.0"


class TestFullDocumentIntegrationOrigin:
    """Integration: parse a complete realistic Origin.xml and validate every field."""

    def test_full_origin_all_fields(self) -> None:
        result = XmlMetadataParser().parse_origin(_FULL_ORIGIN_XML)

        # 2a. PackageProperties
        assert result.contains_exported_data is True

        # 2b. Operation
        assert result.export_timestamp == "2025-06-15T09:22:47.1234567+00:00"
        assert result.product_version == "162.1.167.1"

        # 2c. Server
        assert result.server_version == "16.00.4165"

        # 2d. ObjectCounts — all 8 entries present and correct
        assert result.object_counts == {
            "Table": 48,
            "View": 3,
            "Procedure": 42,
            "SimpleColumn": 636,
            "ScalarFunction": 7,
            "Schema": 5,
            "Sequence": 2,
            "Index": 19,
        }

        # 2e. ExportStatistics
        assert result.source_database_size_kb == 131072
        assert result.total_row_count == 250000

        # 2f. Checksums — picks only /model.xml from 3 entries
        assert result.model_checksum == "e3b0c44298fc1c149afbf4c8996fb924"

        # 2g. ModelSchemaVersion
        assert result.model_schema_version == "2.9"


# ---------------------------------------------------------------------------
# Graceful degradation — malformed values logged and skipped
# ---------------------------------------------------------------------------


class TestParseOriginMalformedObjectCount:
    """Edge case: non-integer text in ObjectCounts is skipped with a warning."""

    def test_non_integer_count_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        xml = _origin_xml(
            "<ObjectCounts>"
            "<Table>48</Table>"
            "<View>not_a_number</View>"
            "<Procedure>10</Procedure>"
            "</ObjectCounts>"
        )
        with caplog.at_level(logging.WARNING, logger="parsing.metadata_parser"):
            result = XmlMetadataParser().parse_origin(xml)
        assert result.object_counts == {"Table": 48, "Procedure": 10}
        assert any("View" in r.message for r in caplog.records)

    def test_all_malformed_counts_yield_empty_dict(self) -> None:
        xml = _origin_xml(
            "<ObjectCounts>"
            "<Table>abc</Table>"
            "</ObjectCounts>"
        )
        result = XmlMetadataParser().parse_origin(xml)
        assert result.object_counts == {}


class TestParseOriginMalformedExportStatistics:
    """Edge case: non-integer ExportStatistics values are skipped with a warning."""

    def test_malformed_size_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        xml = _origin_xml(
            "<ExportStatistics>"
            "<SourceDatabaseSize>not_a_number</SourceDatabaseSize>"
            "<TableRowCountTotalTag>50000</TableRowCountTotalTag>"
            "</ExportStatistics>"
        )
        with caplog.at_level(logging.WARNING, logger="parsing.metadata_parser"):
            result = XmlMetadataParser().parse_origin(xml)
        assert result.source_database_size_kb is None
        assert result.total_row_count == 50000
        assert any("SourceDatabaseSize" in r.message for r in caplog.records)

    def test_malformed_row_count_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        xml = _origin_xml(
            "<ExportStatistics>"
            "<SourceDatabaseSize>1024</SourceDatabaseSize>"
            "<TableRowCountTotalTag>abc</TableRowCountTotalTag>"
            "</ExportStatistics>"
        )
        with caplog.at_level(logging.WARNING, logger="parsing.metadata_parser"):
            result = XmlMetadataParser().parse_origin(xml)
        assert result.source_database_size_kb == 1024
        assert result.total_row_count is None
        assert any("TableRowCountTotalTag" in r.message for r in caplog.records)
