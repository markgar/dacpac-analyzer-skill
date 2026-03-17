"""Concrete ZIP-based package extractor for dacpac/bacpac archives."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from constants import (
    CONTENT_TYPES_XML,
    DAC_METADATA_XML,
    DAC_NAMESPACE,
    MODEL_XML,
    ORIGIN_XML,
)
from errors import (
    InvalidArchiveError,
    MissingEntryError,
    PackageFileNotFoundError,
)
from interfaces.protocols import PackageExtractor
from models.enums import PackageFormat
from models.package import ExtractionResult

logger = logging.getLogger(__name__)

_REQUIRED_ENTRIES: tuple[str, ...] = (MODEL_XML, DAC_METADATA_XML, ORIGIN_XML)


class ZipPackageExtractor(PackageExtractor):
    """Extract file entries from a dacpac/bacpac ZIP archive.

    Validates the archive structure, detects the package format, and
    returns raw file content without any XML parsing of the domain model.
    """

    def extract(self, path: Path) -> ExtractionResult:
        """Extract required entries from the archive.

        Raises:
            PackageFileNotFoundError: If the file does not exist.
            InvalidArchiveError: If the file is not a valid ZIP archive.
            MissingEntryError: If a required entry is missing.
        """
        path = Path(path)

        if not path.exists():
            raise PackageFileNotFoundError(path)

        if not zipfile.is_zipfile(path):
            raise InvalidArchiveError(path)

        with zipfile.ZipFile(path, "r") as zf:
            entry_names = tuple(zf.namelist())

            for required in _REQUIRED_ENTRIES:
                if required not in entry_names:
                    raise MissingEntryError(path, required)

            model_xml = zf.read(MODEL_XML)
            dac_metadata_xml = zf.read(DAC_METADATA_XML)
            origin_xml = zf.read(ORIGIN_XML)

            self._log_unexpected_entries(entry_names)

            pkg_format = self._detect_format(path, entry_names, origin_xml)

        return ExtractionResult(
            format=pkg_format,
            model_xml=model_xml,
            dac_metadata_xml=dac_metadata_xml,
            origin_xml=origin_xml,
            file_list=entry_names,
        )

    @staticmethod
    def _detect_format(
        path: Path,
        entry_names: tuple[str, ...],
        origin_xml: bytes,
    ) -> PackageFormat:
        """Determine whether the archive is a dacpac or bacpac.

        Uses three complementary signals:
        1. File extension
        2. Presence of Data/ folder entries
        3. Origin.xml ContainsExportedData element
        """
        extension = path.suffix.lower()
        has_data_entries = any(name.startswith("Data/") for name in entry_names)
        contains_exported_data = _parse_contains_exported_data(origin_xml)

        if extension == ".bacpac" or has_data_entries or contains_exported_data:
            return PackageFormat.BACPAC
        return PackageFormat.DACPAC

    @staticmethod
    def _log_unexpected_entries(entry_names: tuple[str, ...]) -> None:
        """Log any entries that are not well-known package files at debug level."""
        known = {
            MODEL_XML,
            DAC_METADATA_XML,
            ORIGIN_XML,
            CONTENT_TYPES_XML,
            "_rels/.rels",
        }
        for name in entry_names:
            if name not in known and not name.startswith("Data/"):
                logger.debug("Unexpected archive entry: %s", name)


def _parse_contains_exported_data(origin_xml: bytes) -> bool:
    """Check Origin.xml for the ContainsExportedData element.

    Returns True only if the element text is explicitly 'true'.
    Uses namespace-aware parsing per constitution requirements.
    """
    try:
        root = ET.fromstring(origin_xml)  # noqa: S314
        tag = f"{{{DAC_NAMESPACE}}}ContainsExportedData"
        elem = root.find(f".//{tag}")
        if elem is not None and elem.text:
            return elem.text.strip().lower() == "true"
    except ET.ParseError:
        logger.warning("Failed to parse Origin.xml for format detection")
    return False
