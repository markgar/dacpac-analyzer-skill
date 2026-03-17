"""Abstract interfaces for dacpac/bacpac processing.

All interfaces use abc.ABC with @abstractmethod to enforce that:
- They cannot be instantiated directly.
- Concrete implementations must provide all required methods.
- Any concrete implementation is substitutable wherever the interface is expected.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from models.package import (
        ExtractionResult,
        ModelParseResult,
        Package,
        PackageMetadata,
        PackageOrigin,
    )


class PackageReader(ABC):
    """Read a dacpac or bacpac file into a fully populated Package model."""

    @abstractmethod
    def read_package(self, path: Path) -> Package:
        """Given a file path to a dacpac or bacpac, return a Package model."""


class PackageExtractor(ABC):
    """Extract file entries from a dacpac/bacpac archive."""

    @abstractmethod
    def extract(self, path: Path) -> ExtractionResult:
        """Extract required entries from the archive, returning an ExtractionResult."""


class MetadataParser(ABC):
    """Parse DacMetadata.xml and Origin.xml content."""

    @abstractmethod
    def parse_metadata(self, content: bytes) -> PackageMetadata:
        """Parse DacMetadata.xml content into a PackageMetadata model."""

    @abstractmethod
    def parse_origin(self, content: bytes) -> PackageOrigin:
        """Parse Origin.xml content into a PackageOrigin model."""


class ModelParser(ABC):
    """Parse model.xml content into a complete database model."""

    @abstractmethod
    def parse(self, content: bytes) -> ModelParseResult:
        """Parse model.xml content into a ModelParseResult.

        Returns a single immutable result containing the DatabaseModel
        and root attributes (format_version, schema_version, dsp_name).
        """


class ElementExtractor(ABC):
    """Extract typed domain model instances from raw XML elements.

    Each concrete extractor handles one specific model.xml element type.
    """

    @property
    @abstractmethod
    def element_type(self) -> str:
        """The model.xml Type value this extractor handles."""

    @abstractmethod
    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[Any, ...]:
        """Extract typed domain models from XML elements of the handled type."""
