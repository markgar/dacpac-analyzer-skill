"""Concrete metadata parsers for DacMetadata.xml and Origin.xml.

XmlMetadataParser implements the MetadataParser interface,
extracting typed models from raw XML bytes using namespace-aware access.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from constants import DAC_NAMESPACE
from interfaces.protocols import MetadataParser
from models.package import PackageMetadata, PackageOrigin

logger = logging.getLogger(__name__)


def _ns(tag: str) -> str:
    """Return a fully namespace-qualified tag name."""
    return f"{{{DAC_NAMESPACE}}}{tag}"


class XmlMetadataParser(MetadataParser):
    """Parse DacMetadata.xml and Origin.xml using ElementTree."""

    def parse_metadata(self, content: bytes) -> PackageMetadata:
        """Parse DacMetadata.xml content into a PackageMetadata model.

        Raises ValueError if required elements (Name, Version) are missing.
        """
        root = ET.fromstring(content)

        name_elem = root.find(_ns("Name"))
        if name_elem is None or name_elem.text is None:
            raise ValueError("DacMetadata.xml missing required <Name> element")

        version_elem = root.find(_ns("Version"))
        if version_elem is None or version_elem.text is None:
            raise ValueError("DacMetadata.xml missing required <Version> element")

        return PackageMetadata(
            name=name_elem.text,
            version=version_elem.text,
        )

    def parse_origin(self, content: bytes) -> PackageOrigin:
        """Parse Origin.xml content into a PackageOrigin model.

        Missing optional sections yield None; missing ObjectCounts
        yields an empty tuple.
        """
        root = ET.fromstring(content)

        # 2a. PackageProperties
        contains_exported_data = False
        pkg_props = root.find(_ns("PackageProperties"))
        if pkg_props is not None:
            ced_elem = pkg_props.find(_ns("ContainsExportedData"))
            if ced_elem is not None and ced_elem.text is not None:
                contains_exported_data = ced_elem.text.lower() == "true"

        # 2b. Operation
        export_timestamp: str | None = None
        product_version: str | None = None
        operation = root.find(_ns("Operation"))
        if operation is not None:
            start_elem = operation.find(_ns("Start"))
            if start_elem is not None and start_elem.text is not None:
                export_timestamp = start_elem.text
            pv_elem = operation.find(_ns("ProductVersion"))
            if pv_elem is not None and pv_elem.text is not None:
                product_version = pv_elem.text

        # 2c. Server
        server_version: str | None = None
        server = root.find(_ns("Server"))
        if server is not None:
            sv_elem = server.find(_ns("ServerVersion"))
            if sv_elem is not None and sv_elem.text is not None:
                server_version = sv_elem.text

        # 2d. ObjectCounts
        object_counts: tuple[tuple[str, int], ...] = ()
        obj_counts_elem = root.find(_ns("ObjectCounts"))
        if obj_counts_elem is not None:
            counts: list[tuple[str, int]] = []
            ns_prefix = f"{{{DAC_NAMESPACE}}}"
            for child in obj_counts_elem:
                tag = child.tag
                if tag.startswith(ns_prefix):
                    tag = tag[len(ns_prefix):]
                if child.text is not None:
                    try:
                        counts.append((tag, int(child.text)))
                    except ValueError:
                        logger.warning(
                            "Non-integer object count for <%s>: %r — skipped",
                            tag,
                            child.text,
                        )
            object_counts = tuple(counts)

        # 2e. ExportStatistics
        source_database_size_kb: int | None = None
        total_row_count: int | None = None
        export_stats = root.find(_ns("ExportStatistics"))
        if export_stats is not None:
            size_elem = export_stats.find(_ns("SourceDatabaseSize"))
            if size_elem is not None and size_elem.text is not None:
                try:
                    source_database_size_kb = int(size_elem.text)
                except ValueError:
                    logger.warning(
                        "Non-integer SourceDatabaseSize: %r — skipped",
                        size_elem.text,
                    )
            row_elem = export_stats.find(_ns("TableRowCountTotalTag"))
            if row_elem is not None and row_elem.text is not None:
                try:
                    total_row_count = int(row_elem.text)
                except ValueError:
                    logger.warning(
                        "Non-integer TableRowCountTotalTag: %r — skipped",
                        row_elem.text,
                    )

        # 2f. Checksums
        model_checksum: str | None = None
        checksums = root.find(_ns("Checksums"))
        if checksums is not None:
            for checksum_elem in checksums.findall(_ns("Checksum")):
                if checksum_elem.get("Uri") == "/model.xml":
                    model_checksum = checksum_elem.text
                    break

        # 2g. ModelSchemaVersion
        model_schema_version: str | None = None
        msv_elem = root.find(_ns("ModelSchemaVersion"))
        if msv_elem is not None and msv_elem.text is not None:
            model_schema_version = msv_elem.text

        return PackageOrigin(
            contains_exported_data=contains_exported_data,
            server_version=server_version,
            product_version=product_version,
            _object_counts=object_counts,
            source_database_size_kb=source_database_size_kb,
            total_row_count=total_row_count,
            model_checksum=model_checksum,
            model_schema_version=model_schema_version,
            export_timestamp=export_timestamp,
        )
