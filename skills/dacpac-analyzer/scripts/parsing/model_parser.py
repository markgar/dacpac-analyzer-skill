"""Concrete ModelParser that orchestrates model.xml parsing.

Ties together root attribute extraction, element scanning, parsing
context construction, extractor registry dispatch, and DatabaseModel
assembly.
"""

from __future__ import annotations

import logging
from xml.etree import ElementTree

from constants import DAC_NAMESPACE
from interfaces.protocols import ModelParser
from models.domain import DatabaseOptions
from models.enums import ElementType
from models.package import DatabaseModel, ModelParseResult
from parsing.context import scan_elements
from parsing.registry import ExtractorRegistry

logger = logging.getLogger(__name__)

_NS = f"{{{DAC_NAMESPACE}}}"

_DATABASE_OPTIONS_TYPE = ElementType.DATABASE_OPTIONS.value

# Mapping from ElementType to DatabaseModel field names.
# Only types that map to top-level DatabaseModel collection fields are included.
# SqlDatabaseOptions is handled separately — it is a singleton, not a collection.
_TYPE_TO_FIELD: dict[str, str] = {
    ElementType.SCHEMA.value: "schemas",
    ElementType.TABLE.value: "tables",
    ElementType.VIEW.value: "views",
    ElementType.PROCEDURE.value: "procedures",
    ElementType.SCALAR_FUNCTION.value: "scalar_functions",
    ElementType.INLINE_TVF.value: "inline_tvfs",
    ElementType.SEQUENCE.value: "sequences",
    ElementType.TABLE_TYPE.value: "table_types",
    ElementType.ROLE.value: "roles",
    ElementType.PERMISSION.value: "permissions",
    ElementType.FILEGROUP.value: "filegroups",
    ElementType.PARTITION_FUNCTION.value: "partition_functions",
    ElementType.PARTITION_SCHEME.value: "partition_schemes",
    ElementType.PRIMARY_KEY.value: "primary_keys",
    ElementType.UNIQUE_CONSTRAINT.value: "unique_constraints",
    ElementType.FOREIGN_KEY.value: "foreign_keys",
    ElementType.CHECK_CONSTRAINT.value: "check_constraints",
    ElementType.DEFAULT_CONSTRAINT.value: "default_constraints",
    ElementType.INDEX.value: "indexes",
    ElementType.COLUMNSTORE_INDEX.value: "indexes",
    ElementType.EXTENDED_PROPERTY.value: "extended_properties",
}


class XmlModelParser(ModelParser):
    """Parse model.xml content into a ModelParseResult.

    Uses an ``ExtractorRegistry`` (dependency injection) for element-type
    dispatch. Stateless — each ``parse()`` call returns a self-contained
    ``ModelParseResult`` with the DatabaseModel and root attributes.
    """

    def __init__(self, registry: ExtractorRegistry) -> None:
        self._registry = registry

    def parse(self, content: bytes) -> ModelParseResult:
        """Parse model.xml content into a ModelParseResult.

        Orchestrates:
        1. Parse root ``<DataSchemaModel>`` attributes.
        2. Scan all ``<Element>`` nodes — build groups and name index.
        3. Construct the parsing context.
        4. Dispatch extractors via registry.
        5. Assemble the ``ModelParseResult``.
        """
        root = ElementTree.fromstring(content)

        # Step 1: Extract root attributes
        format_version = root.get("FileFormatVersion", "")
        schema_version = root.get("SchemaVersion", "")
        dsp_name = root.get("DspName", "")
        collation_lcid = root.get("CollationLcid")
        collation_case_sensitive = root.get("CollationCaseSensitive")

        # Step 2 & 3: Scan elements and build context
        model_elem = root.find(f"{_NS}Model")
        if model_elem is None:
            logger.warning("No <Model> element found in model.xml — returning empty DatabaseModel")
            return ModelParseResult(
                database_model=DatabaseModel(database_options=None),
                format_version=format_version,
                schema_version=schema_version,
                dsp_name=dsp_name,
            )

        context = scan_elements(model_elem)

        # Step 4: Dispatch extractors
        extraction_results = self._registry.dispatch(context)

        # Step 5: Assemble DatabaseModel
        #
        # SqlDatabaseOptions is a singleton — not a collection field.
        # Merge extracted properties with root collation attributes.
        db_options = _build_database_options(
            extraction_results.pop(_DATABASE_OPTIONS_TYPE, None),
            collation_lcid,
            collation_case_sensitive,
        )
        model_kwargs: dict[str, object] = {"database_options": db_options}

        for type_str, extracted in extraction_results.items():
            field_name = _TYPE_TO_FIELD.get(type_str)
            if field_name is None:
                continue

            if field_name in model_kwargs and isinstance(model_kwargs[field_name], tuple):
                # Merge results for types that map to the same field (e.g. Index + ColumnStoreIndex)
                existing = model_kwargs[field_name]
                model_kwargs[field_name] = existing + extracted  # type: ignore[operator]
            else:
                model_kwargs[field_name] = extracted

        return ModelParseResult(
            database_model=DatabaseModel(**model_kwargs),  # type: ignore[arg-type]
            format_version=format_version,
            schema_version=schema_version,
            dsp_name=dsp_name,
        )


def _build_database_options(
    extracted: tuple[DatabaseOptions, ...] | None,
    collation_lcid: str | None,
    collation_case_sensitive: str | None,
) -> DatabaseOptions | None:
    """Build ``DatabaseOptions`` by merging extractor output with root attributes.

    Returns ``None`` if no ``SqlDatabaseOptions`` element was extracted.
    When present, the first extracted element's properties are merged with
    root-level collation attributes.
    """
    if extracted is None or len(extracted) == 0:
        return None

    base = extracted[0]
    return DatabaseOptions(
        _properties=base._properties,
        collation_lcid=collation_lcid,
        collation_case_sensitive=collation_case_sensitive,
    )
