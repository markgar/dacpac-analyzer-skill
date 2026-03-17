"""Tests for aggregate models, package models, and abstract interfaces."""

from pathlib import Path
from typing import Any, Sequence

import pytest

from interfaces.protocols import (
    ElementExtractor,
    MetadataParser,
    ModelParser,
    PackageExtractor,
    PackageReader,
)
from models.domain import (
    CheckConstraint,
    DatabaseOptions,
    DefaultConstraint,
    ExtendedProperty,
    Filegroup,
    ForeignKey,
    Index,
    InlineTableValuedFunction,
    PartitionFunction,
    PartitionScheme,
    Permission,
    PrimaryKey,
    Procedure,
    Role,
    ScalarFunction,
    Schema,
    Sequence as SequenceModel,
    Table,
    TableType,
    UniqueConstraint,
    View,
)
from models.package import (
    DatabaseModel,
    Package,
    PackageMetadata,
    PackageOrigin,
)
from parsing.name_parser import parse_name


class TestDatabaseModel:
    """AC 6: DatabaseModel with empty lists is valid without null checks."""

    def test_empty_construction(self) -> None:
        model = DatabaseModel()
        assert model.database_options is None
        assert model.schemas == ()
        assert model.tables == ()
        assert model.views == ()
        assert model.procedures == ()
        assert model.scalar_functions == ()
        assert model.inline_tvfs == ()
        assert model.sequences == ()
        assert model.table_types == ()
        assert model.roles == ()
        assert model.permissions == ()
        assert model.filegroups == ()
        assert model.partition_functions == ()
        assert model.partition_schemes == ()
        assert model.primary_keys == ()
        assert model.unique_constraints == ()
        assert model.foreign_keys == ()
        assert model.check_constraints == ()
        assert model.default_constraints == ()
        assert model.indexes == ()
        assert model.extended_properties == ()

    def test_all_collections_iterable_without_null_checks(self) -> None:
        """Empty DatabaseModel collections can be iterated directly."""
        model = DatabaseModel()
        total = (
            len(model.schemas)
            + len(model.tables)
            + len(model.views)
            + len(model.procedures)
            + len(model.scalar_functions)
            + len(model.inline_tvfs)
            + len(model.sequences)
            + len(model.table_types)
            + len(model.roles)
            + len(model.permissions)
            + len(model.filegroups)
            + len(model.partition_functions)
            + len(model.partition_schemes)
            + len(model.primary_keys)
            + len(model.unique_constraints)
            + len(model.foreign_keys)
            + len(model.check_constraints)
            + len(model.default_constraints)
            + len(model.indexes)
            + len(model.extended_properties)
        )
        assert total == 0

    def test_with_populated_collections(self) -> None:
        schema = Schema(
            name=parse_name("[dbo]"),
            authorizer=parse_name("[dbo]"),
        )
        table = Table(
            name=parse_name("[dbo].[T]"),
            schema_ref=parse_name("[dbo]"),
        )
        model = DatabaseModel(
            schemas=(schema,),
            tables=(table,),
        )
        assert len(model.schemas) == 1
        assert len(model.tables) == 1
        assert model.schemas[0].name.parts == ("dbo",)

    def test_immutability(self) -> None:
        model = DatabaseModel()
        with pytest.raises(AttributeError):
            model.schemas = ()  # type: ignore[misc]

    def test_with_database_options(self) -> None:
        opts = DatabaseOptions(
            _properties=(("Compat", "150"),),
            collation_lcid="1033",
        )
        model = DatabaseModel(database_options=opts)
        assert model.database_options is not None
        assert model.database_options.collation_lcid == "1033"


class TestPackageMetadata:
    def test_construction(self) -> None:
        meta = PackageMetadata(name="MyDb", version="1.0.0")
        assert meta.name == "MyDb"
        assert meta.version == "1.0.0"

    def test_immutability(self) -> None:
        meta = PackageMetadata(name="MyDb", version="1.0.0")
        with pytest.raises(AttributeError):
            meta.name = "Other"  # type: ignore[misc]


class TestPackageOrigin:
    def test_defaults(self) -> None:
        origin = PackageOrigin()
        assert origin.contains_exported_data is False
        assert origin.server_version is None
        assert origin.product_version is None
        assert origin.object_counts == {}
        assert origin.source_database_size_kb is None
        assert origin.total_row_count is None
        assert origin.model_checksum is None
        assert origin.model_schema_version is None
        assert origin.export_timestamp is None

    def test_with_object_counts(self) -> None:
        origin = PackageOrigin(
            contains_exported_data=True,
            server_version="15.0.2000.5",
            _object_counts=(("SqlTable", 10), ("SqlView", 3)),
            source_database_size_kb=51200,
            total_row_count=100000,
        )
        assert origin.contains_exported_data is True
        assert origin.object_counts == {"SqlTable": 10, "SqlView": 3}
        assert origin.source_database_size_kb == 51200

    def test_immutability(self) -> None:
        origin = PackageOrigin()
        with pytest.raises(AttributeError):
            origin.contains_exported_data = True  # type: ignore[misc]


class TestPackage:
    def test_construction(self) -> None:
        pkg = Package(
            metadata=PackageMetadata(name="MyDb", version="1.0.0"),
            origin=PackageOrigin(),
            database_model=DatabaseModel(),
            format_version="3.1",
            schema_version="2.7",
            dsp_name="Microsoft.Data.Tools.Schema.Sql.Sql150DatabaseSchemaProvider",
        )
        assert pkg.metadata.name == "MyDb"
        assert pkg.origin.contains_exported_data is False
        assert pkg.database_model.tables == ()
        assert pkg.format_version == "3.1"
        assert pkg.schema_version == "2.7"

    def test_immutability(self) -> None:
        pkg = Package(
            metadata=PackageMetadata(name="MyDb", version="1.0.0"),
            origin=PackageOrigin(),
            database_model=DatabaseModel(),
            format_version="3.1",
            schema_version="2.7",
            dsp_name="Provider",
        )
        with pytest.raises(AttributeError):
            pkg.format_version = "4.0"  # type: ignore[misc]


class TestProtocolsCannotBeInstantiated:
    """AC 8: Abstract interfaces cannot be instantiated directly."""

    def test_package_reader(self) -> None:
        with pytest.raises(TypeError):
            PackageReader()  # type: ignore[abstract]

    def test_package_extractor(self) -> None:
        with pytest.raises(TypeError):
            PackageExtractor()  # type: ignore[abstract]

    def test_metadata_parser(self) -> None:
        with pytest.raises(TypeError):
            MetadataParser()  # type: ignore[abstract]

    def test_model_parser(self) -> None:
        with pytest.raises(TypeError):
            ModelParser()  # type: ignore[abstract]

    def test_element_extractor(self) -> None:
        with pytest.raises(TypeError):
            ElementExtractor()  # type: ignore[abstract]


class TestProtocolsSubstitutable:
    """AC 8: Concrete implementations are substitutable for the interface."""

    def test_package_reader_substitutable(self) -> None:
        class ConcreteReader(PackageReader):
            def read_package(self, path: Path) -> Any:
                return None

        reader: PackageReader = ConcreteReader()
        assert isinstance(reader, PackageReader)

    def test_package_extractor_substitutable(self) -> None:
        class ConcreteExtractor(PackageExtractor):
            def extract(self, path: Path) -> dict[str, bytes]:
                return {}

        extractor: PackageExtractor = ConcreteExtractor()
        assert isinstance(extractor, PackageExtractor)

    def test_metadata_parser_substitutable(self) -> None:
        class ConcreteMetaParser(MetadataParser):
            def parse_metadata(self, content: bytes) -> Any:
                return None

            def parse_origin(self, content: bytes) -> Any:
                return None

        parser: MetadataParser = ConcreteMetaParser()
        assert isinstance(parser, MetadataParser)

    def test_model_parser_substitutable(self) -> None:
        class ConcreteModelParser(ModelParser):
            def parse(self, content: bytes) -> Any:
                return None

        parser: ModelParser = ConcreteModelParser()
        assert isinstance(parser, ModelParser)

    def test_element_extractor_substitutable(self) -> None:
        class ConcreteElementExtractor(ElementExtractor):
            @property
            def element_type(self) -> str:
                return "SqlTable"

            def extract(
                self, elements: Sequence[Any], context: Any
            ) -> list[Any]:
                return []

        extractor: ElementExtractor = ConcreteElementExtractor()
        assert isinstance(extractor, ElementExtractor)
        assert extractor.element_type == "SqlTable"
