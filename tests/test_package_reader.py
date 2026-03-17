"""Tests for the PackageReader orchestrator and composition root factory.

Covers:
- AC 5: Mock-based delegation test (each collaborator invoked exactly once)
- Error propagation: extraction, metadata, model parser errors
- Factory: create_package_reader returns properly wired instance
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from errors import PackageFileNotFoundError
from interfaces.protocols import (
    MetadataParser,
    ModelParser,
    PackageExtractor,
    PackageReader,
)
from models.package import (
    DatabaseModel,
    ExtractionResult,
    ModelParseResult,
    Package,
    PackageMetadata,
    PackageOrigin,
)
from models.enums import PackageFormat
from orchestration.factory import create_package_reader
from orchestration.package_reader import DacpacPackageReader


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def extraction_result() -> ExtractionResult:
    """A minimal ExtractionResult with dummy bytes."""
    return ExtractionResult(
        format=PackageFormat.DACPAC,
        model_xml=b"<model/>",
        dac_metadata_xml=b"<metadata/>",
        origin_xml=b"<origin/>",
        file_list=("model.xml", "DacMetadata.xml", "Origin.xml"),
    )


@pytest.fixture()
def metadata() -> PackageMetadata:
    return PackageMetadata(name="TestDB", version="1.0.0")


@pytest.fixture()
def origin() -> PackageOrigin:
    return PackageOrigin(contains_exported_data=False)


@pytest.fixture()
def database_model() -> DatabaseModel:
    return DatabaseModel()


@pytest.fixture()
def mock_extractor(extraction_result: ExtractionResult) -> MagicMock:
    mock = MagicMock(spec=PackageExtractor)
    mock.extract.return_value = extraction_result
    return mock


@pytest.fixture()
def mock_metadata_parser(
    metadata: PackageMetadata, origin: PackageOrigin
) -> MagicMock:
    mock = MagicMock(spec=MetadataParser)
    mock.parse_metadata.return_value = metadata
    mock.parse_origin.return_value = origin
    return mock


@pytest.fixture()
def mock_model_parser(database_model: DatabaseModel) -> MagicMock:
    mock = MagicMock(spec=ModelParser)
    mock.parse.return_value = ModelParseResult(
        database_model=database_model,
        format_version="2.0",
        schema_version="2.5",
        dsp_name="Microsoft.Data.Tools.Schema.Sql.Sql160DatabaseSchemaProvider",
    )
    return mock


@pytest.fixture()
def reader(
    mock_extractor: MagicMock,
    mock_metadata_parser: MagicMock,
    mock_model_parser: MagicMock,
) -> DacpacPackageReader:
    return DacpacPackageReader(
        extractor=mock_extractor,
        metadata_parser=mock_metadata_parser,
        model_parser=mock_model_parser,
    )


# ── AC 5: Delegation — each collaborator invoked exactly once ─────────

class TestDelegation:
    """AC 5: Each collaborator is invoked exactly once with correct input."""

    def test_extractor_called_once_with_path(
        self, reader: DacpacPackageReader, mock_extractor: MagicMock
    ) -> None:
        path = Path("/some/package.dacpac")
        reader.read_package(path)
        mock_extractor.extract.assert_called_once_with(path)

    def test_metadata_parser_called_once_with_dac_metadata_xml(
        self,
        reader: DacpacPackageReader,
        mock_metadata_parser: MagicMock,
        extraction_result: ExtractionResult,
    ) -> None:
        reader.read_package(Path("/some/package.dacpac"))
        mock_metadata_parser.parse_metadata.assert_called_once_with(
            extraction_result.dac_metadata_xml,
        )

    def test_origin_parser_called_once_with_origin_xml(
        self,
        reader: DacpacPackageReader,
        mock_metadata_parser: MagicMock,
        extraction_result: ExtractionResult,
    ) -> None:
        reader.read_package(Path("/some/package.dacpac"))
        mock_metadata_parser.parse_origin.assert_called_once_with(
            extraction_result.origin_xml,
        )

    def test_model_parser_called_once_with_model_xml(
        self,
        reader: DacpacPackageReader,
        mock_model_parser: MagicMock,
        extraction_result: ExtractionResult,
    ) -> None:
        reader.read_package(Path("/some/package.dacpac"))
        mock_model_parser.parse.assert_called_once_with(
            extraction_result.model_xml,
        )


class TestPackageAssembly:
    """Verify the assembled Package has fields from all collaborators."""

    def test_package_has_metadata(
        self,
        reader: DacpacPackageReader,
        metadata: PackageMetadata,
    ) -> None:
        pkg = reader.read_package(Path("/x.dacpac"))
        assert pkg.metadata is metadata

    def test_package_has_origin(
        self,
        reader: DacpacPackageReader,
        origin: PackageOrigin,
    ) -> None:
        pkg = reader.read_package(Path("/x.dacpac"))
        assert pkg.origin is origin

    def test_package_has_database_model(
        self,
        reader: DacpacPackageReader,
        database_model: DatabaseModel,
    ) -> None:
        pkg = reader.read_package(Path("/x.dacpac"))
        assert pkg.database_model is database_model

    def test_package_has_format_version_from_model_parser(
        self, reader: DacpacPackageReader
    ) -> None:
        pkg = reader.read_package(Path("/x.dacpac"))
        assert pkg.format_version == "2.0"

    def test_package_has_schema_version_from_model_parser(
        self, reader: DacpacPackageReader
    ) -> None:
        pkg = reader.read_package(Path("/x.dacpac"))
        assert pkg.schema_version == "2.5"

    def test_package_has_dsp_name_from_model_parser(
        self, reader: DacpacPackageReader
    ) -> None:
        pkg = reader.read_package(Path("/x.dacpac"))
        assert pkg.dsp_name == "Microsoft.Data.Tools.Schema.Sql.Sql160DatabaseSchemaProvider"

    def test_empty_root_attributes_default_to_empty_string(
        self,
        mock_extractor: MagicMock,
        mock_metadata_parser: MagicMock,
    ) -> None:
        """When model parser result has empty root attributes, Package fields are empty strings."""
        mock_mp = MagicMock(spec=ModelParser)
        mock_mp.parse.return_value = ModelParseResult(
            database_model=DatabaseModel(),
        )

        reader = DacpacPackageReader(
            extractor=mock_extractor,
            metadata_parser=mock_metadata_parser,
            model_parser=mock_mp,
        )
        pkg = reader.read_package(Path("/x.dacpac"))
        assert pkg.format_version == ""
        assert pkg.schema_version == ""
        assert pkg.dsp_name == ""


# ── Error propagation ─────────────────────────────────────────────────

class TestErrorPropagation:
    """Error propagation per spec §4."""

    def test_extraction_error_propagates_as_is(
        self,
        mock_extractor: MagicMock,
        mock_metadata_parser: MagicMock,
        mock_model_parser: MagicMock,
    ) -> None:
        """Extraction errors propagate without wrapping."""
        mock_extractor.extract.side_effect = PackageFileNotFoundError(
            Path("/no/such.dacpac")
        )
        reader = DacpacPackageReader(
            extractor=mock_extractor,
            metadata_parser=mock_metadata_parser,
            model_parser=mock_model_parser,
        )
        with pytest.raises(PackageFileNotFoundError):
            reader.read_package(Path("/no/such.dacpac"))

    def test_metadata_parse_error_wrapped_with_context(
        self,
        mock_extractor: MagicMock,
        mock_metadata_parser: MagicMock,
        mock_model_parser: MagicMock,
    ) -> None:
        """MetadataParser error wraps with file context."""
        mock_metadata_parser.parse_metadata.side_effect = ValueError("bad xml")
        reader = DacpacPackageReader(
            extractor=mock_extractor,
            metadata_parser=mock_metadata_parser,
            model_parser=mock_model_parser,
        )
        with pytest.raises(ValueError, match="Failed to parse DacMetadata.xml"):
            reader.read_package(Path("/x.dacpac"))

    def test_origin_parse_error_wrapped_with_context(
        self,
        mock_extractor: MagicMock,
        mock_metadata_parser: MagicMock,
        mock_model_parser: MagicMock,
    ) -> None:
        """Origin parser error wraps with file context."""
        mock_metadata_parser.parse_origin.side_effect = ValueError("bad xml")
        reader = DacpacPackageReader(
            extractor=mock_extractor,
            metadata_parser=mock_metadata_parser,
            model_parser=mock_model_parser,
        )
        with pytest.raises(ValueError, match="Failed to parse Origin.xml"):
            reader.read_package(Path("/x.dacpac"))

    def test_model_parse_error_wrapped_with_context(
        self,
        mock_extractor: MagicMock,
        mock_metadata_parser: MagicMock,
        mock_model_parser: MagicMock,
    ) -> None:
        """Model parser error wraps with file context."""
        mock_model_parser.parse.side_effect = ValueError("bad model")
        reader = DacpacPackageReader(
            extractor=mock_extractor,
            metadata_parser=mock_metadata_parser,
            model_parser=mock_model_parser,
        )
        with pytest.raises(ValueError, match="Failed to parse model.xml"):
            reader.read_package(Path("/x.dacpac"))

    def test_metadata_error_chain_preserves_cause(
        self,
        mock_extractor: MagicMock,
        mock_metadata_parser: MagicMock,
        mock_model_parser: MagicMock,
    ) -> None:
        """Wrapped errors preserve the original exception as __cause__."""
        original = ValueError("underlying problem")
        mock_metadata_parser.parse_metadata.side_effect = original
        reader = DacpacPackageReader(
            extractor=mock_extractor,
            metadata_parser=mock_metadata_parser,
            model_parser=mock_model_parser,
        )
        with pytest.raises(ValueError) as exc_info:
            reader.read_package(Path("/x.dacpac"))
        assert exc_info.value.__cause__ is original


# ── Factory ───────────────────────────────────────────────────────────

class TestCreatePackageReader:
    """Test the composition root factory."""

    def test_returns_package_reader(self) -> None:
        reader = create_package_reader()
        assert isinstance(reader, PackageReader)

    def test_returns_dacpac_package_reader(self) -> None:
        reader = create_package_reader()
        assert isinstance(reader, DacpacPackageReader)

    def test_factory_wires_all_collaborators(self) -> None:
        """The factory returns a reader with functional collaborators."""
        reader = create_package_reader()
        assert isinstance(reader, DacpacPackageReader)
        # Verify internal wiring by checking collaborator types
        assert reader._extractor is not None
        assert reader._metadata_parser is not None
        assert reader._model_parser is not None


# ═══════════════════════════════════════════════════════════════════════
# Integration tests — real dacpac/bacpac archives through the full pipeline
# ═══════════════════════════════════════════════════════════════════════

import io
import logging
import zipfile

from constants import (
    DAC_METADATA_XML,
    DAC_NAMESPACE,
    MODEL_XML,
    ORIGIN_XML,
)

_NS = DAC_NAMESPACE

_ROOT_ATTRS = (
    f'xmlns="{_NS}" '
    'FileFormatVersion="1.2" '
    'SchemaVersion="2.9" '
    'DspName="Microsoft.Data.Tools.Schema.Sql.Sql130DatabaseSchemaProvider" '
    'CollationLcid="1033" '
    'CollationCaseSensitive="False"'
)


def _dac_metadata_xml(name: str = "TestDB", version: str = "1.0.0.0") -> bytes:
    """Build a minimal DacMetadata.xml."""
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<DacType xmlns="{_NS}">'
        f"<Name>{name}</Name>"
        f"<Version>{version}</Version>"
        f"</DacType>"
    ).encode("utf-8")


def _origin_xml_dacpac() -> bytes:
    """Build Origin.xml for a dacpac (ContainsExportedData=false)."""
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<DacOrigin xmlns="{_NS}">'
        f"<PackageProperties>"
        f"<ContainsExportedData>false</ContainsExportedData>"
        f"</PackageProperties>"
        f"</DacOrigin>"
    ).encode("utf-8")


def _origin_xml_bacpac() -> bytes:
    """Build Origin.xml for a bacpac (ContainsExportedData=true)."""
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<DacOrigin xmlns="{_NS}">'
        f"<PackageProperties>"
        f"<ContainsExportedData>true</ContainsExportedData>"
        f"</PackageProperties>"
        f"</DacOrigin>"
    ).encode("utf-8")


def _model_xml_with_elements(elements: str) -> bytes:
    """Wrap element XML fragments into a complete model.xml document."""
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f"<DataSchemaModel {_ROOT_ATTRS}>"
        f"<Model>{elements}</Model>"
        f"</DataSchemaModel>"
    ).encode("utf-8")


def _realistic_model_xml() -> bytes:
    """Build a realistic model.xml with tables, columns, constraints, and schemas."""
    elements = (
        # Schema
        '<Element Type="SqlSchema" Name="[dbo]">'
        '<Relationship Name="Authorizer">'
        "<Entry>"
        '<References Name="[dbo]" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
        # Table with columns and a primary key
        '<Element Type="SqlTable" Name="[dbo].[Users]">'
        '<Relationship Name="Schema">'
        "<Entry>"
        '<References Name="[dbo]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="Columns">'
        "<Entry>"
        '<Element Type="SqlSimpleColumn" Name="[dbo].[Users].[Id]">'
        '<Property Name="IsNullable" Value="False" />'
        '<Property Name="IsIdentity" Value="True" />'
        '<Relationship Name="TypeSpecifier">'
        "<Entry>"
        '<References Name="[int]" ExternalSource="BuiltIns" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
        "</Entry>"
        "<Entry>"
        '<Element Type="SqlSimpleColumn" Name="[dbo].[Users].[Name]">'
        '<Property Name="IsNullable" Value="False" />'
        '<Relationship Name="TypeSpecifier">'
        "<Entry>"
        '<Property Name="Length" Value="100" />'
        '<References Name="[nvarchar]" ExternalSource="BuiltIns" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
        "</Entry>"
        "</Relationship>"
        "</Element>"
        # Primary key constraint
        '<Element Type="SqlPrimaryKeyConstraint" Name="[dbo].[PK_Users]">'
        '<Relationship Name="DefiningTable">'
        "<Entry>"
        '<References Name="[dbo].[Users]" />'
        "</Entry>"
        "</Relationship>"
        '<Relationship Name="ColumnSpecifications">'
        "<Entry>"
        '<Element Type="SqlIndexedColumnSpecification">'
        '<Relationship Name="Column">'
        "<Entry>"
        '<References Name="[dbo].[Users].[Id]" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
        "</Entry>"
        "</Relationship>"
        "</Element>"
        # Check constraint
        '<Element Type="SqlCheckConstraint" Name="[dbo].[CK_Users_Name]">'
        '<Property Name="ExpressionScript">'
        "<Value><![CDATA[LEN([Name]) > 0]]></Value>"
        "</Property>"
        '<Relationship Name="DefiningTable">'
        "<Entry>"
        '<References Name="[dbo].[Users]" />'
        "</Entry>"
        "</Relationship>"
        "</Element>"
    )
    return _model_xml_with_elements(elements)


def _build_zip_archive(
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


def _dacpac_entries(
    model_xml: bytes | None = None,
    metadata_xml: bytes | None = None,
) -> dict[str, bytes]:
    """Return entries for a dacpac archive with realistic content."""
    return {
        MODEL_XML: model_xml if model_xml is not None else _realistic_model_xml(),
        DAC_METADATA_XML: metadata_xml if metadata_xml is not None else _dac_metadata_xml(),
        ORIGIN_XML: _origin_xml_dacpac(),
    }


def _bacpac_entries(
    model_xml: bytes | None = None,
    metadata_xml: bytes | None = None,
) -> dict[str, bytes]:
    """Return entries for a bacpac archive with realistic content."""
    entries: dict[str, bytes] = {
        MODEL_XML: model_xml if model_xml is not None else _realistic_model_xml(),
        DAC_METADATA_XML: metadata_xml if metadata_xml is not None else _dac_metadata_xml(),
        ORIGIN_XML: _origin_xml_bacpac(),
    }
    entries["Data/dbo.Users.BCP"] = b"bcp-data"
    return entries


# ── AC 1: Valid dacpac → Package with all fields populated ────────────

class TestIntegrationAC1DacpacFullPipeline:
    """AC 1: GIVEN a valid .dacpac file containing well-formed model.xml,
    DacMetadata.xml, and Origin.xml WHEN read_package(path) is called
    THEN a Package model is returned with all fields populated.
    """

    def test_metadata_name_is_non_empty(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert pkg.metadata.name == "TestDB"
        assert pkg.metadata.name != ""

    def test_metadata_version(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert pkg.metadata.version == "1.0.0.0"

    def test_origin_contains_exported_data_false(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert pkg.origin.contains_exported_data is False

    def test_database_model_has_tables(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert len(pkg.database_model.tables) >= 1
        assert pkg.database_model.tables[0].name.parts == ("dbo", "Users")

    def test_database_model_has_columns(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        table = pkg.database_model.tables[0]
        assert len(table.columns) >= 2

    def test_database_model_has_primary_key(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert len(pkg.database_model.primary_keys) >= 1
        pk = pkg.database_model.primary_keys[0]
        assert pk.name.parts == ("dbo", "PK_Users")

    def test_database_model_has_check_constraint(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert len(pkg.database_model.check_constraints) >= 1

    def test_database_model_has_schema(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert len(pkg.database_model.schemas) >= 1
        assert pkg.database_model.schemas[0].name.parts == ("dbo",)

    def test_format_version_populated(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert pkg.format_version == "1.2"

    def test_schema_version_populated(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert pkg.schema_version == "2.9"

    def test_dsp_name_populated(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert pkg.dsp_name == "Microsoft.Data.Tools.Schema.Sql.Sql130DatabaseSchemaProvider"


# ── AC 2: Valid bacpac → contains_exported_data is True ───────────────

class TestIntegrationAC2BacpacFullPipeline:
    """AC 2: GIVEN a valid .bacpac file WHEN read_package(path) is called
    THEN origin.contains_exported_data is True and the database_model is
    fully populated.
    """

    def test_origin_contains_exported_data_true(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(
            _bacpac_entries(), extension=".bacpac", tmp_path=tmp_path,
        )
        pkg = create_package_reader().read_package(archive)
        assert pkg.origin.contains_exported_data is True

    def test_database_model_is_populated(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(
            _bacpac_entries(), extension=".bacpac", tmp_path=tmp_path,
        )
        pkg = create_package_reader().read_package(archive)
        assert len(pkg.database_model.tables) >= 1
        assert len(pkg.database_model.schemas) >= 1

    def test_metadata_populated(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(
            _bacpac_entries(), extension=".bacpac", tmp_path=tmp_path,
        )
        pkg = create_package_reader().read_package(archive)
        assert pkg.metadata.name == "TestDB"


# ── AC 3: Non-existent path → typed error from extraction layer ──────

class TestIntegrationAC3NonExistentPath:
    """AC 3: GIVEN a file path to a non-existent file WHEN read_package(path)
    is called THEN a typed error is raised from the extraction layer.
    """

    def test_raises_package_file_not_found_error(self) -> None:
        reader = create_package_reader()
        with pytest.raises(PackageFileNotFoundError):
            reader.read_package(Path("/nonexistent/path/missing.dacpac"))

    def test_error_preserves_path(self) -> None:
        reader = create_package_reader()
        bad_path = Path("/tmp/does_not_exist.dacpac")
        with pytest.raises(PackageFileNotFoundError) as exc_info:
            reader.read_package(bad_path)
        assert exc_info.value.path == bad_path


# ── AC 4: Determinism — same dacpac twice → identical results ────────

class TestIntegrationAC4Determinism:
    """AC 4: GIVEN the same dacpac file processed twice WHEN read_package(path)
    is called both times THEN the resulting Package models are structurally
    identical.
    """

    def test_same_file_produces_identical_packages(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        reader = create_package_reader()
        pkg1 = reader.read_package(archive)
        pkg2 = reader.read_package(archive)
        assert pkg1 == pkg2

    def test_metadata_identical(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        reader = create_package_reader()
        pkg1 = reader.read_package(archive)
        pkg2 = reader.read_package(archive)
        assert pkg1.metadata == pkg2.metadata

    def test_origin_identical(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        reader = create_package_reader()
        pkg1 = reader.read_package(archive)
        pkg2 = reader.read_package(archive)
        assert pkg1.origin == pkg2.origin

    def test_database_model_identical(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        reader = create_package_reader()
        pkg1 = reader.read_package(archive)
        pkg2 = reader.read_package(archive)
        assert pkg1.database_model == pkg2.database_model

    def test_root_attributes_identical(self, tmp_path: Path) -> None:
        archive = _build_zip_archive(_dacpac_entries(), tmp_path=tmp_path)
        reader = create_package_reader()
        pkg1 = reader.read_package(archive)
        pkg2 = reader.read_package(archive)
        assert pkg1.format_version == pkg2.format_version
        assert pkg1.schema_version == pkg2.schema_version
        assert pkg1.dsp_name == pkg2.dsp_name


# ── AC 6: Unknown element types → Package returned, warnings logged ──

class TestIntegrationAC6UnknownElementTypes:
    """AC 6: GIVEN a dacpac with a model.xml containing unknown element types
    WHEN read_package(path) is called THEN the Package is returned successfully
    with known types populated; warnings are logged for unknown types.
    """

    def _model_xml_with_unknown(self) -> bytes:
        """Build model.xml with both known and unknown element types."""
        elements = (
            '<Element Type="SqlSchema" Name="[dbo]">'
            '<Relationship Name="Authorizer">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            "</Element>"
            # Unknown element type — should be skipped with a warning
            '<Element Type="SqlFutureWidget" Name="[dbo].[MyWidget]">'
            '<Property Name="Foo" Value="Bar" />'
            "</Element>"
            # Another unknown type
            '<Element Type="SqlGadget" Name="[dbo].[MyGadget]" />'
        )
        return _model_xml_with_elements(elements)

    def test_package_returned_with_known_types(self, tmp_path: Path) -> None:
        entries = _dacpac_entries(model_xml=self._model_xml_with_unknown())
        archive = _build_zip_archive(entries, tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert len(pkg.database_model.schemas) == 1
        assert pkg.database_model.schemas[0].name.parts == ("dbo",)

    def test_warnings_logged_for_unknown_types(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        entries = _dacpac_entries(model_xml=self._model_xml_with_unknown())
        archive = _build_zip_archive(entries, tmp_path=tmp_path)
        with caplog.at_level(logging.WARNING, logger="parsing"):
            create_package_reader().read_package(archive)
        warning_messages = " ".join(r.message for r in caplog.records)
        assert "SqlFutureWidget" in warning_messages or "SqlGadget" in warning_messages

    def test_package_metadata_still_populated(self, tmp_path: Path) -> None:
        entries = _dacpac_entries(model_xml=self._model_xml_with_unknown())
        archive = _build_zip_archive(entries, tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert pkg.metadata.name == "TestDB"
        assert pkg.origin.contains_exported_data is False


# ── Edge case: empty model.xml (no elements) ─────────────────────────

class TestIntegrationEdgeCaseEmptyModel:
    """Edge case: model.xml with no elements → Package returned with empty DatabaseModel."""

    def test_empty_model_returns_package(self, tmp_path: Path) -> None:
        empty_model = _model_xml_with_elements("")
        entries = _dacpac_entries(model_xml=empty_model)
        archive = _build_zip_archive(entries, tmp_path=tmp_path)
        pkg = create_package_reader().read_package(archive)
        assert pkg.database_model.tables == ()
        assert pkg.database_model.schemas == ()
        assert pkg.metadata.name == "TestDB"
