"""Tests for core domain models — immutability and construction."""

import pytest

from models.domain import (
    CheckConstraint,
    Column,
    DataCompressionOption,
    DatabaseOptions,
    DefaultConstraint,
    ExtendedProperty,
    Filegroup,
    ForeignKey,
    Index,
    IndexedColumn,
    InlineTableValuedFunction,
    Parameter,
    PartitionFunction,
    PartitionScheme,
    Permission,
    PrimaryKey,
    Procedure,
    Role,
    ScalarFunction,
    Schema,
    Sequence,
    Table,
    TableType,
    TypeSpecifier,
    UniqueConstraint,
    View,
)
from models.enums import (
    CompressionLevel,
    Durability,
    PartitionRange,
    SortOrder,
)
from models.parsed_name import ParsedName
from parsing.name_parser import parse_name


def _name(raw: str) -> ParsedName:
    """Shorthand for creating ParsedName instances in tests."""
    return parse_name(raw)


class TestTypeSpecifier:
    """AC 5: TypeSpecifier fields accessible and immutable."""

    def test_all_fields_accessible(self) -> None:
        ts = TypeSpecifier(
            type_name="nvarchar", length=60, is_builtin=True
        )
        assert ts.type_name == "nvarchar"
        assert ts.length == 60
        assert ts.is_builtin is True
        assert ts.precision is None
        assert ts.scale is None
        assert ts.is_max is False

    def test_immutability_rejected(self) -> None:
        ts = TypeSpecifier(type_name="int", is_builtin=True)
        with pytest.raises(AttributeError):
            ts.type_name = "bigint"  # type: ignore[misc]

    def test_decimal_type(self) -> None:
        ts = TypeSpecifier(
            type_name="decimal", is_builtin=True, precision=18, scale=2
        )
        assert ts.precision == 18
        assert ts.scale == 2

    def test_max_length(self) -> None:
        ts = TypeSpecifier(
            type_name="varchar", is_builtin=True, is_max=True
        )
        assert ts.is_max is True
        assert ts.length is None


class TestColumn:
    def test_basic_column(self) -> None:
        col = Column(
            name=_name("[dbo].[T].[Col1]"),
            ordinal=0,
            type_specifier=TypeSpecifier(type_name="int", is_builtin=True),
        )
        assert col.name.sub_name == "Col1"
        assert col.ordinal == 0
        assert col.is_nullable is True
        assert col.is_computed is False

    def test_computed_column(self) -> None:
        col = Column(
            name=_name("[dbo].[T].[Calc]"),
            ordinal=1,
            type_specifier=TypeSpecifier(type_name="int", is_builtin=True),
            is_computed=True,
            expression_script="[Col1] + 1",
            is_persisted=True,
        )
        assert col.is_computed is True
        assert col.expression_script == "[Col1] + 1"
        assert col.is_persisted is True

    def test_computed_column_without_type_specifier(self) -> None:
        col = Column(
            name=_name("[dbo].[T].[Calc]"),
            ordinal=0,
            is_computed=True,
            expression_script="[A] + [B]",
        )
        assert col.type_specifier is None
        assert col.is_computed is True

    def test_immutability(self) -> None:
        col = Column(
            name=_name("[dbo].[T].[Col1]"),
            ordinal=0,
            type_specifier=TypeSpecifier(type_name="int", is_builtin=True),
        )
        with pytest.raises(AttributeError):
            col.ordinal = 5  # type: ignore[misc]


class TestIndexedColumn:
    def test_defaults_to_ascending(self) -> None:
        ic = IndexedColumn(column_ref=_name("[dbo].[T].[Col1]"))
        assert ic.sort_order is SortOrder.ASCENDING

    def test_descending(self) -> None:
        ic = IndexedColumn(
            column_ref=_name("[dbo].[T].[Col1]"),
            sort_order=SortOrder.DESCENDING,
        )
        assert ic.sort_order is SortOrder.DESCENDING


class TestPrimaryKey:
    def test_empty_columns(self) -> None:
        pk = PrimaryKey(
            name=_name("[dbo].[PK_T]"),
            defining_table=_name("[dbo].[T]"),
        )
        assert pk.columns == ()
        assert pk.filegroup is None


class TestUniqueConstraint:
    def test_same_shape_as_primary_key(self) -> None:
        uc = UniqueConstraint(
            name=_name("[dbo].[UQ_T]"),
            defining_table=_name("[dbo].[T]"),
            columns=(
                IndexedColumn(column_ref=_name("[dbo].[T].[Col1]")),
            ),
        )
        assert len(uc.columns) == 1


class TestForeignKey:
    def test_construction(self) -> None:
        fk = ForeignKey(
            name=_name("[dbo].[FK_Child_Parent]"),
            defining_table=_name("[dbo].[Child]"),
            columns=(_name("[dbo].[Child].[ParentID]"),),
            foreign_table=_name("[dbo].[Parent]"),
            foreign_columns=(_name("[dbo].[Parent].[ID]"),),
        )
        assert len(fk.columns) == 1
        assert fk.foreign_table is not None


class TestCheckConstraint:
    def test_construction(self) -> None:
        cc = CheckConstraint(
            name=_name("[dbo].[CK_T]"),
            defining_table=_name("[dbo].[T]"),
            expression="[Col1] > 0",
        )
        assert cc.expression == "[Col1] > 0"


class TestDefaultConstraint:
    def test_construction(self) -> None:
        dc = DefaultConstraint(
            name=_name("[dbo].[DF_T_Col1]"),
            defining_table=_name("[dbo].[T]"),
            for_column=_name("[dbo].[T].[Col1]"),
            expression="0",
        )
        assert dc.expression == "0"
        assert dc.for_column is not None


class TestIndex:
    def test_non_columnstore(self) -> None:
        idx = Index(
            name=_name("[dbo].[IX_T_Col1]"),
            indexed_object=_name("[dbo].[T]"),
        )
        assert idx.is_columnstore is False
        assert idx.columns == ()

    def test_columnstore(self) -> None:
        idx = Index(
            name=_name("[dbo].[CCI_T]"),
            indexed_object=_name("[dbo].[T]"),
            is_columnstore=True,
        )
        assert idx.is_columnstore is True


class TestDataCompressionOption:
    def test_defaults(self) -> None:
        opt = DataCompressionOption()
        assert opt.compression_level is CompressionLevel.NONE
        assert opt.partition_number is None

    def test_page_compression(self) -> None:
        opt = DataCompressionOption(
            compression_level=CompressionLevel.PAGE, partition_number=1
        )
        assert opt.compression_level is CompressionLevel.PAGE
        assert opt.partition_number == 1


class TestTable:
    def test_minimal_table(self) -> None:
        t = Table(
            name=_name("[dbo].[T]"),
            schema_ref=_name("[dbo]"),
        )
        assert t.columns == ()
        assert t.is_memory_optimized is False
        assert t.durability is None
        assert t.compression_options == ()

    def test_memory_optimized_table(self) -> None:
        t = Table(
            name=_name("[dbo].[T]"),
            schema_ref=_name("[dbo]"),
            is_memory_optimized=True,
            durability=Durability.SCHEMA_AND_DATA,
        )
        assert t.is_memory_optimized is True
        assert t.durability is Durability.SCHEMA_AND_DATA

    def test_immutability(self) -> None:
        t = Table(
            name=_name("[dbo].[T]"),
            schema_ref=_name("[dbo]"),
        )
        with pytest.raises(AttributeError):
            t.is_memory_optimized = True  # type: ignore[misc]


class TestView:
    def test_construction(self) -> None:
        v = View(
            name=_name("[dbo].[V]"),
            schema_ref=_name("[dbo]"),
            query_script="SELECT 1",
        )
        assert v.query_script == "SELECT 1"
        assert v.columns == ()


class TestParameter:
    def test_input_param(self) -> None:
        p = Parameter(
            name=_name("[dbo].[Proc].[@P1]"),
            type_specifier=TypeSpecifier(type_name="int", is_builtin=True),
        )
        assert p.is_output is False

    def test_output_param(self) -> None:
        p = Parameter(
            name=_name("[dbo].[Proc].[@P1]"),
            type_specifier=TypeSpecifier(type_name="int", is_builtin=True),
            is_output=True,
        )
        assert p.is_output is True


class TestProcedure:
    def test_construction(self) -> None:
        proc = Procedure(
            name=_name("[dbo].[MyProc]"),
            schema_ref=_name("[dbo]"),
            body_script="SELECT 1",
        )
        assert proc.parameters == ()
        assert proc.body_dependencies == ()
        assert proc.execute_as is None


class TestScalarFunction:
    def test_construction(self) -> None:
        fn = ScalarFunction(
            name=_name("[dbo].[MyFn]"),
            schema_ref=_name("[dbo]"),
            return_type=TypeSpecifier(type_name="int", is_builtin=True),
            body_script="RETURN 1",
        )
        assert fn.return_type is not None
        assert fn.parameters == ()


class TestInlineTableValuedFunction:
    def test_construction(self) -> None:
        fn = InlineTableValuedFunction(
            name=_name("[dbo].[MyTVF]"),
            schema_ref=_name("[dbo]"),
            body_script="RETURN SELECT 1 AS X",
        )
        assert fn.columns == ()
        assert fn.parameters == ()


class TestSequence:
    def test_construction(self) -> None:
        seq = Sequence(
            name=_name("[dbo].[Seq1]"),
            schema_ref=_name("[dbo]"),
            type_specifier=TypeSpecifier(type_name="bigint", is_builtin=True),
            start_value="1",
            increment="1",
        )
        assert seq.current_value is None


class TestTableType:
    def test_construction(self) -> None:
        tt = TableType(
            name=_name("[dbo].[MyTT]"),
            schema_ref=_name("[dbo]"),
        )
        assert tt.columns == ()
        assert tt.primary_key is None


class TestRole:
    def test_construction(self) -> None:
        role = Role(
            name=_name("[db_owner]"),
            authorizer=_name("[dbo]"),
        )
        assert role.name.parts == ("db_owner",)


class TestPermission:
    def test_construction(self) -> None:
        perm = Permission(
            permission_code="195",
            grantee=_name("[SomeRole]"),
        )
        assert perm.name is None
        assert perm.secured_object is None

    def test_with_secured_object(self) -> None:
        perm = Permission(
            permission_code="195",
            grantee=_name("[SomeRole]"),
            secured_object=_name("[dbo].[T]"),
        )
        assert perm.secured_object is not None


class TestSchema:
    def test_construction(self) -> None:
        s = Schema(
            name=_name("[dbo]"),
            authorizer=_name("[dbo]"),
        )
        assert s.name.parts == ("dbo",)


class TestFilegroup:
    def test_defaults(self) -> None:
        fg = Filegroup(name=_name("[PRIMARY]"))
        assert fg.contains_memory_optimized_data is False

    def test_memory_optimized(self) -> None:
        fg = Filegroup(
            name=_name("[InMemory]"),
            contains_memory_optimized_data=True,
        )
        assert fg.contains_memory_optimized_data is True


class TestPartitionFunction:
    def test_construction(self) -> None:
        pf = PartitionFunction(
            name=_name("[PF_Date]"),
            range_type=PartitionRange.RIGHT,
            parameter_type=TypeSpecifier(type_name="date", is_builtin=True),
            boundary_values=("2020-01-01", "2021-01-01"),
        )
        assert len(pf.boundary_values) == 2
        assert pf.range_type is PartitionRange.RIGHT


class TestPartitionScheme:
    def test_construction(self) -> None:
        ps = PartitionScheme(
            name=_name("[PS_Date]"),
            partition_function=_name("[PF_Date]"),
            filegroups=(_name("[FG1]"), _name("[FG2]")),
        )
        assert len(ps.filegroups) == 2


class TestExtendedProperty:
    def test_construction(self) -> None:
        ep = ExtendedProperty(
            name=_name("[SqlColumn].[dbo].[T].[Col1].[Description]"),
            host=_name("[dbo].[T].[Col1]"),
            value="Column description",
        )
        assert ep.value == "Column description"


class TestDatabaseOptions:
    def test_empty(self) -> None:
        opts = DatabaseOptions()
        assert opts.properties == {}
        assert opts.collation_lcid is None

    def test_with_properties(self) -> None:
        opts = DatabaseOptions(
            _properties=(("Compatibility", "150"), ("ANSI_NULLS", "ON")),
            collation_lcid="1033",
        )
        assert opts.properties == {"Compatibility": "150", "ANSI_NULLS": "ON"}
        assert opts.collation_lcid == "1033"

    def test_immutability(self) -> None:
        opts = DatabaseOptions()
        with pytest.raises(AttributeError):
            opts.collation_lcid = "1033"  # type: ignore[misc]


class TestAllModelsImmutable:
    """AC 7: All domain models reject mutation after construction."""

    def test_type_specifier(self) -> None:
        obj = TypeSpecifier(type_name="int", is_builtin=True)
        with pytest.raises(AttributeError):
            obj.type_name = "x"  # type: ignore[misc]

    def test_column(self) -> None:
        obj = Column(
            name=_name("[dbo].[T].[C]"),
            ordinal=0,
            type_specifier=TypeSpecifier(type_name="int", is_builtin=True),
        )
        with pytest.raises(AttributeError):
            obj.ordinal = 1  # type: ignore[misc]

    def test_indexed_column(self) -> None:
        obj = IndexedColumn(column_ref=_name("[dbo].[T].[C]"))
        with pytest.raises(AttributeError):
            obj.sort_order = SortOrder.DESCENDING  # type: ignore[misc]

    def test_primary_key(self) -> None:
        obj = PrimaryKey(name=_name("[dbo].[PK]"), defining_table=_name("[dbo].[T]"))
        with pytest.raises(AttributeError):
            obj.filegroup = _name("[FG]")  # type: ignore[misc]

    def test_foreign_key(self) -> None:
        obj = ForeignKey(
            name=_name("[dbo].[FK]"),
            defining_table=_name("[dbo].[T]"),
            foreign_table=_name("[dbo].[X]"),
        )
        with pytest.raises(AttributeError):
            obj.foreign_table = _name("[dbo].[Y]")  # type: ignore[misc]

    def test_table(self) -> None:
        obj = Table(name=_name("[dbo].[T]"), schema_ref=_name("[dbo]"))
        with pytest.raises(AttributeError):
            obj.is_memory_optimized = True  # type: ignore[misc]

    def test_view(self) -> None:
        obj = View(name=_name("[dbo].[V]"), schema_ref=_name("[dbo]"))
        with pytest.raises(AttributeError):
            obj.query_script = "x"  # type: ignore[misc]

    def test_procedure(self) -> None:
        obj = Procedure(name=_name("[dbo].[P]"), schema_ref=_name("[dbo]"))
        with pytest.raises(AttributeError):
            obj.body_script = "x"  # type: ignore[misc]

    def test_schema(self) -> None:
        obj = Schema(name=_name("[dbo]"), authorizer=_name("[dbo]"))
        with pytest.raises(AttributeError):
            obj.authorizer = _name("[sa]")  # type: ignore[misc]

    def test_role(self) -> None:
        obj = Role(name=_name("[r]"), authorizer=_name("[dbo]"))
        with pytest.raises(AttributeError):
            obj.authorizer = _name("[sa]")  # type: ignore[misc]

    def test_sequence(self) -> None:
        obj = Sequence(
            name=_name("[dbo].[S]"),
            schema_ref=_name("[dbo]"),
            type_specifier=TypeSpecifier(type_name="bigint", is_builtin=True),
        )
        with pytest.raises(AttributeError):
            obj.start_value = "99"  # type: ignore[misc]

    def test_extended_property(self) -> None:
        obj = ExtendedProperty(
            name=_name("[dbo].[T].[C]"),
            host=_name("[dbo].[T]"),
        )
        with pytest.raises(AttributeError):
            obj.value = "x"  # type: ignore[misc]
