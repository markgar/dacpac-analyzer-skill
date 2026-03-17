"""Tests for Spec 02 — Package Extraction (ZIP/OPC Archive Handling).

Tests cover all six acceptance criteria plus edge cases for the
ZipPackageExtractor and its supporting models and errors.
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

import pytest

from constants import DAC_METADATA_XML, MODEL_XML, ORIGIN_XML
from errors import (
    InvalidArchiveError,
    MissingEntryError,
    PackageError,
    PackageFileNotFoundError,
)
from extraction import ZipPackageExtractor
from models.enums import PackageFormat
from models.package import ExtractionResult


# ---------------------------------------------------------------------------
# Fixture helpers — build in-memory ZIP archives
# ---------------------------------------------------------------------------

_MINIMAL_ORIGIN_DACPAC = (
    b'<?xml version="1.0" encoding="utf-8"?>'
    b'<DacOrigin xmlns="http://schemas.microsoft.com/sqlserver/dac/Serialization/2012/02">'
    b"<ContainsExportedData>false</ContainsExportedData>"
    b"</DacOrigin>"
)

_MINIMAL_ORIGIN_BACPAC = (
    b'<?xml version="1.0" encoding="utf-8"?>'
    b'<DacOrigin xmlns="http://schemas.microsoft.com/sqlserver/dac/Serialization/2012/02">'
    b"<ContainsExportedData>true</ContainsExportedData>"
    b"</DacOrigin>"
)

_MINIMAL_MODEL = b'<root>model</root>'
_MINIMAL_DAC_METADATA = b'<root>metadata</root>'


def _build_zip(
    entries: dict[str, bytes],
    *,
    extension: str = ".dacpac",
    tmp_path: Path,
    name: str = "test",
) -> Path:
    """Create a ZIP archive on disk with the given entries."""
    dest = tmp_path / f"{name}{extension}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry_name, content in entries.items():
            zf.writestr(entry_name, content)
    dest.write_bytes(buf.getvalue())
    return dest


def _required_entries(
    *,
    origin: bytes = _MINIMAL_ORIGIN_DACPAC,
) -> dict[str, bytes]:
    """Return a dict containing the three required archive entries."""
    return {
        MODEL_XML: _MINIMAL_MODEL,
        DAC_METADATA_XML: _MINIMAL_DAC_METADATA,
        ORIGIN_XML: origin,
    }


# ---------------------------------------------------------------------------
# AC1: Valid dacpac — format DACPAC, contents present, file_list complete
# ---------------------------------------------------------------------------


class TestAC1ValidDacpac:
    """AC1: GIVEN a valid .dacpac file containing the three required files
    WHEN the extractor is invoked
    THEN format is DACPAC, all three contents are present, file_list enumerates all ZIP entries.
    """

    def test_format_is_dacpac(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert result.format is PackageFormat.DACPAC

    def test_model_xml_content(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert result.model_xml == _MINIMAL_MODEL

    def test_dac_metadata_content(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert result.dac_metadata_xml == _MINIMAL_DAC_METADATA

    def test_origin_xml_content(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert result.origin_xml == _MINIMAL_ORIGIN_DACPAC

    def test_file_list_enumerates_all_entries(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert set(result.file_list) == {MODEL_XML, DAC_METADATA_XML, ORIGIN_XML}

    def test_file_list_is_tuple(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert isinstance(result.file_list, tuple)

    def test_result_is_extraction_result(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert isinstance(result, ExtractionResult)


# ---------------------------------------------------------------------------
# AC2: Valid bacpac — format BACPAC, Data/ entries in file_list only
# ---------------------------------------------------------------------------


class TestAC2ValidBacpac:
    """AC2: GIVEN a valid .bacpac file with required files plus Data/ entries
    WHEN the extractor is invoked
    THEN format is BACPAC, Data/ entries appear in file_list but not in content fields.
    """

    def _make_bacpac(self, tmp_path: Path) -> Path:
        entries = _required_entries(origin=_MINIMAL_ORIGIN_BACPAC)
        entries["Data/dbo.Users.BCP"] = b"bcp-data"
        entries["Data/dbo.Orders.BCP"] = b"more-bcp-data"
        return _build_zip(entries, extension=".bacpac", tmp_path=tmp_path)

    def test_format_is_bacpac(self, tmp_path: Path) -> None:
        result = ZipPackageExtractor().extract(self._make_bacpac(tmp_path))
        assert result.format is PackageFormat.BACPAC

    def test_data_entries_in_file_list(self, tmp_path: Path) -> None:
        result = ZipPackageExtractor().extract(self._make_bacpac(tmp_path))
        data_entries = [f for f in result.file_list if f.startswith("Data/")]
        assert len(data_entries) == 2
        assert "Data/dbo.Users.BCP" in data_entries
        assert "Data/dbo.Orders.BCP" in data_entries

    def test_data_entries_not_in_content_fields(self, tmp_path: Path) -> None:
        result = ZipPackageExtractor().extract(self._make_bacpac(tmp_path))
        # Content fields only contain the three required files
        assert result.model_xml == _MINIMAL_MODEL
        assert result.dac_metadata_xml == _MINIMAL_DAC_METADATA
        assert result.origin_xml == _MINIMAL_ORIGIN_BACPAC

    def test_bacpac_detected_by_data_entries_and_origin(self, tmp_path: Path) -> None:
        """A .dacpac extension with Data/ entries should still be BACPAC."""
        entries = _required_entries(origin=_MINIMAL_ORIGIN_BACPAC)
        entries["Data/dbo.Table.BCP"] = b"data"
        archive = _build_zip(entries, extension=".dacpac", tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert result.format is PackageFormat.BACPAC


# ---------------------------------------------------------------------------
# AC3: Nonexistent path — typed error with path
# ---------------------------------------------------------------------------


class TestAC3NonexistentPath:
    """AC3: GIVEN a file path that does not exist
    WHEN the extractor is invoked
    THEN a typed error is raised containing the missing path.
    """

    def test_raises_package_file_not_found_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.dacpac"
        with pytest.raises(PackageFileNotFoundError) as exc_info:
            ZipPackageExtractor().extract(missing)
        assert exc_info.value.path == missing

    def test_error_is_package_error_subclass(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.dacpac"
        with pytest.raises(PackageError):
            ZipPackageExtractor().extract(missing)

    def test_error_message_contains_path(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.dacpac"
        with pytest.raises(PackageFileNotFoundError, match="nonexistent.dacpac"):
            ZipPackageExtractor().extract(missing)


# ---------------------------------------------------------------------------
# AC4: Non-ZIP file — InvalidArchiveError
# ---------------------------------------------------------------------------


class TestAC4NonZipFile:
    """AC4: GIVEN a file that is not a valid ZIP archive
    WHEN the extractor is invoked
    THEN a typed error is raised indicating the file is not a valid archive.
    """

    def test_raises_invalid_archive_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "not_a_zip.dacpac"
        bad_file.write_text("this is plain text, not a ZIP")
        with pytest.raises(InvalidArchiveError) as exc_info:
            ZipPackageExtractor().extract(bad_file)
        assert exc_info.value.path == bad_file

    def test_error_is_package_error_subclass(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "corrupt.dacpac"
        bad_file.write_bytes(b"\x00\x01\x02\x03")
        with pytest.raises(PackageError):
            ZipPackageExtractor().extract(bad_file)

    def test_empty_file_raises_invalid_archive(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.dacpac"
        empty.write_bytes(b"")
        with pytest.raises(InvalidArchiveError):
            ZipPackageExtractor().extract(empty)


# ---------------------------------------------------------------------------
# AC5: ZIP missing model.xml — MissingEntryError naming model.xml
# ---------------------------------------------------------------------------


class TestAC5MissingModelXml:
    """AC5: GIVEN a ZIP archive that is missing model.xml
    WHEN the extractor is invoked
    THEN a typed error is raised specifically naming model.xml.
    """

    def test_raises_missing_entry_error(self, tmp_path: Path) -> None:
        entries = {
            DAC_METADATA_XML: _MINIMAL_DAC_METADATA,
            ORIGIN_XML: _MINIMAL_ORIGIN_DACPAC,
        }
        archive = _build_zip(entries, tmp_path=tmp_path)
        with pytest.raises(MissingEntryError) as exc_info:
            ZipPackageExtractor().extract(archive)
        assert exc_info.value.entry_name == MODEL_XML

    def test_error_message_names_model_xml(self, tmp_path: Path) -> None:
        entries = {
            DAC_METADATA_XML: _MINIMAL_DAC_METADATA,
            ORIGIN_XML: _MINIMAL_ORIGIN_DACPAC,
        }
        archive = _build_zip(entries, tmp_path=tmp_path)
        with pytest.raises(MissingEntryError, match="model.xml"):
            ZipPackageExtractor().extract(archive)

    def test_error_is_package_error_subclass(self, tmp_path: Path) -> None:
        entries = {
            DAC_METADATA_XML: _MINIMAL_DAC_METADATA,
            ORIGIN_XML: _MINIMAL_ORIGIN_DACPAC,
        }
        archive = _build_zip(entries, tmp_path=tmp_path)
        with pytest.raises(PackageError):
            ZipPackageExtractor().extract(archive)


# ---------------------------------------------------------------------------
# AC6: Extra unexpected entries — succeed, appear in file_list, debug log
# ---------------------------------------------------------------------------


class TestAC6ExtraEntries:
    """AC6: GIVEN a .dacpac file with extra unexpected entries
    WHEN the extractor is invoked
    THEN extraction succeeds, extra files appear in file_list, debug log emitted.
    """

    def test_extraction_succeeds_with_extra_files(self, tmp_path: Path) -> None:
        entries = _required_entries()
        entries["notes.txt"] = b"some notes"
        archive = _build_zip(entries, tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert result.format is PackageFormat.DACPAC

    def test_extra_file_in_file_list(self, tmp_path: Path) -> None:
        entries = _required_entries()
        entries["notes.txt"] = b"some notes"
        archive = _build_zip(entries, tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert "notes.txt" in result.file_list

    def test_debug_log_emitted_for_extra_file(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        entries = _required_entries()
        entries["notes.txt"] = b"some notes"
        archive = _build_zip(entries, tmp_path=tmp_path)
        with caplog.at_level(logging.DEBUG, logger="extraction.zip_extractor"):
            ZipPackageExtractor().extract(archive)
        assert any("notes.txt" in record.message for record in caplog.records)

    def test_known_opc_entries_not_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """[Content_Types].xml and _rels/.rels are known OPC files, not logged."""
        entries = _required_entries()
        entries["[Content_Types].xml"] = b"<Types/>"
        entries["_rels/.rels"] = b"<Relationships/>"
        archive = _build_zip(entries, tmp_path=tmp_path)
        with caplog.at_level(logging.DEBUG, logger="extraction.zip_extractor"):
            ZipPackageExtractor().extract(archive)
        unexpected = [r for r in caplog.records if "Unexpected" in r.message]
        assert len(unexpected) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCaseMissingDacMetadata:
    """Edge case: ZIP missing DacMetadata.xml should raise MissingEntryError."""

    def test_raises_missing_entry_error_for_dac_metadata(self, tmp_path: Path) -> None:
        entries = {
            MODEL_XML: _MINIMAL_MODEL,
            ORIGIN_XML: _MINIMAL_ORIGIN_DACPAC,
        }
        archive = _build_zip(entries, tmp_path=tmp_path)
        with pytest.raises(MissingEntryError) as exc_info:
            ZipPackageExtractor().extract(archive)
        assert exc_info.value.entry_name == DAC_METADATA_XML


class TestEdgeCaseMissingOriginXml:
    """Edge case: ZIP missing Origin.xml should raise MissingEntryError."""

    def test_raises_missing_entry_error_for_origin(self, tmp_path: Path) -> None:
        entries = {
            MODEL_XML: _MINIMAL_MODEL,
            DAC_METADATA_XML: _MINIMAL_DAC_METADATA,
        }
        archive = _build_zip(entries, tmp_path=tmp_path)
        with pytest.raises(MissingEntryError) as exc_info:
            ZipPackageExtractor().extract(archive)
        assert exc_info.value.entry_name == ORIGIN_XML


class TestEdgeCaseEmptyArchive:
    """Edge case: empty ZIP archive (no entries) should raise MissingEntryError."""

    def test_empty_archive_raises_missing_entry(self, tmp_path: Path) -> None:
        archive = _build_zip({}, tmp_path=tmp_path)
        with pytest.raises(MissingEntryError):
            ZipPackageExtractor().extract(archive)


class TestEdgeCaseExtractionResultImmutable:
    """Edge case: ExtractionResult is a frozen dataclass — cannot be mutated."""

    def test_extraction_result_is_frozen(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        with pytest.raises(AttributeError):
            result.format = PackageFormat.BACPAC  # type: ignore[misc]

    def test_extraction_result_slots(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        with pytest.raises((AttributeError, TypeError)):
            result.extra_field = "nope"  # type: ignore[attr-defined]


class TestEdgeCasePathTypes:
    """Edge case: the extractor accepts both str and Path inputs."""

    def test_string_path_accepted(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(str(archive))  # type: ignore[arg-type]
        assert result.format is PackageFormat.DACPAC

    def test_path_object_accepted(self, tmp_path: Path) -> None:
        archive = _build_zip(_required_entries(), tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(Path(archive))
        assert result.format is PackageFormat.DACPAC


class TestEdgeCaseFormatDetectionHeuristics:
    """Edge cases for format detection heuristics."""

    def test_bacpac_extension_without_data_entries(self, tmp_path: Path) -> None:
        """A .bacpac extension alone triggers BACPAC format."""
        entries = _required_entries(origin=_MINIMAL_ORIGIN_DACPAC)
        archive = _build_zip(entries, extension=".bacpac", tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert result.format is PackageFormat.BACPAC

    def test_data_entries_alone_trigger_bacpac(self, tmp_path: Path) -> None:
        """Data/ entries in a .dacpac with dacpac Origin still yield BACPAC."""
        entries = _required_entries(origin=_MINIMAL_ORIGIN_DACPAC)
        entries["Data/dbo.Table.BCP"] = b"data"
        archive = _build_zip(entries, extension=".dacpac", tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert result.format is PackageFormat.BACPAC

    def test_origin_exported_data_true_triggers_bacpac(self, tmp_path: Path) -> None:
        """ContainsExportedData=true in Origin.xml triggers BACPAC."""
        entries = _required_entries(origin=_MINIMAL_ORIGIN_BACPAC)
        archive = _build_zip(entries, extension=".dacpac", tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert result.format is PackageFormat.BACPAC

    def test_malformed_origin_xml_defaults_to_dacpac(self, tmp_path: Path) -> None:
        """If Origin.xml cannot be parsed, format detection still works."""
        entries = _required_entries(origin=b"not valid xml at all")
        archive = _build_zip(entries, extension=".dacpac", tmp_path=tmp_path)
        result = ZipPackageExtractor().extract(archive)
        assert result.format is PackageFormat.DACPAC
