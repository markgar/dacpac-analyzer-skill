"""Abstract interfaces for dacpac/bacpac processing."""

from interfaces.protocols import (
    ElementExtractor,
    MetadataParser,
    ModelParser,
    PackageExtractor,
    PackageReader,
)

__all__ = [
    "ElementExtractor",
    "MetadataParser",
    "ModelParser",
    "PackageExtractor",
    "PackageReader",
]
