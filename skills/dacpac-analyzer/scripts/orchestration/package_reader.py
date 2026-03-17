"""Concrete PackageReader that orchestrates the full pipeline.

Composes PackageExtractor, MetadataParser, and ModelParser into a
sequential pipeline: extract → parse metadata + origin + model → assemble Package.
"""

from __future__ import annotations

import logging
from pathlib import Path

from interfaces.protocols import (
    MetadataParser,
    ModelParser,
    PackageExtractor,
    PackageReader,
)
from models.package import Package

logger = logging.getLogger(__name__)


class DacpacPackageReader(PackageReader):
    """Read a dacpac/bacpac file into a fully populated Package model.

    Receives collaborators via constructor injection — never instantiates
    them directly, satisfying the Dependency Inversion Principle.
    """

    def __init__(
        self,
        extractor: PackageExtractor,
        metadata_parser: MetadataParser,
        model_parser: ModelParser,
    ) -> None:
        self._extractor = extractor
        self._metadata_parser = metadata_parser
        self._model_parser = model_parser

    def read_package(self, path: Path) -> Package:
        """Execute the full pipeline: extract → parse → assemble.

        Error propagation per spec §4:
        - PackageExtractor errors propagate as-is.
        - MetadataParser/ModelParser errors propagate with context.
        - Unknown element types are logged by the extractor layer, not raised.
        """
        # Step 1: Extract raw contents from archive
        extraction = self._extractor.extract(path)

        # Step 2: Parse metadata (DacMetadata.xml)
        try:
            metadata = self._metadata_parser.parse_metadata(
                extraction.dac_metadata_xml,
            )
        except Exception as exc:
            raise ValueError(
                "Failed to parse DacMetadata.xml"
            ) from exc

        # Step 3: Parse origin (Origin.xml)
        try:
            origin = self._metadata_parser.parse_origin(extraction.origin_xml)
        except Exception as exc:
            raise ValueError(
                "Failed to parse Origin.xml"
            ) from exc

        # Step 4: Parse model (model.xml)
        try:
            model_result = self._model_parser.parse(extraction.model_xml)
        except Exception as exc:
            raise ValueError(
                "Failed to parse model.xml"
            ) from exc

        # Step 5: Assemble Package
        return Package(
            metadata=metadata,
            origin=origin,
            database_model=model_result.database_model,
            format_version=model_result.format_version,
            schema_version=model_result.schema_version,
            dsp_name=model_result.dsp_name,
        )
