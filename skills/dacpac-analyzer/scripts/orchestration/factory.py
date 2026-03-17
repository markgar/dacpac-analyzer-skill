"""Composition root for wiring a ready-to-use PackageReader.

Instantiates all concrete collaborators, registers all element extractors,
and returns a fully wired PackageReader. This is the only place that knows
about concrete implementations — all other code depends on abstractions.
"""

from __future__ import annotations

from extraction.zip_extractor import ZipPackageExtractor
from interfaces.protocols import PackageReader
from orchestration.package_reader import DacpacPackageReader
from parsing.extractors import (
    register_spec05_extractors,
    register_spec06_extractors,
    register_spec07_extractors,
    register_spec08_extractors,
    register_spec09_extractors,
)
from parsing.metadata_parser import XmlMetadataParser
from parsing.model_parser import XmlModelParser
from parsing.registry import ExtractorRegistry


def create_package_reader() -> PackageReader:
    """Create a fully wired PackageReader with all extractors registered.

    Wiring sequence per spec §3:
    1. Instantiate ExtractorRegistry and register all element extractors.
    2. Instantiate XmlModelParser with the populated registry.
    3. Instantiate XmlMetadataParser.
    4. Instantiate ZipPackageExtractor.
    5. Wire into DacpacPackageReader and return.
    """
    registry = ExtractorRegistry()
    register_spec05_extractors(registry)
    register_spec06_extractors(registry)
    register_spec07_extractors(registry)
    register_spec08_extractors(registry)
    register_spec09_extractors(registry)

    model_parser = XmlModelParser(registry)
    metadata_parser = XmlMetadataParser()
    package_extractor = ZipPackageExtractor()

    return DacpacPackageReader(
        extractor=package_extractor,
        metadata_parser=metadata_parser,
        model_parser=model_parser,
    )
