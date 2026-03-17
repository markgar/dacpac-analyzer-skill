"""Shared constants for dacpac/bacpac processing."""

from typing import Final

DAC_NAMESPACE: Final[str] = (
    "http://schemas.microsoft.com/sqlserver/dac/Serialization/2012/02"
)

MODEL_XML: Final[str] = "model.xml"
DAC_METADATA_XML: Final[str] = "DacMetadata.xml"
ORIGIN_XML: Final[str] = "Origin.xml"
CONTENT_TYPES_XML: Final[str] = "[Content_Types].xml"
BUILTIN_EXTERNAL_SOURCE: Final[str] = "BuiltIns"
