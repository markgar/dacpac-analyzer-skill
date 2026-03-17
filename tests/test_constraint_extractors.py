"""Tests for constraint extractors (PK, Unique, Foreign Key).

Maps to Spec 07 acceptance criteria for constraint extraction.
"""

from __future__ import annotations

import logging
from xml.etree.ElementTree import Element, SubElement

import pytest

from constants import DAC_NAMESPACE
from models.enums import SortOrder
from parsing.extractors.column_helpers import extract_indexed_columns
from parsing.extractors.constraints import (
    SqlCheckConstraintExtractor,
    SqlDefaultConstraintExtractor,
    SqlForeignKeyConstraintExtractor,
    SqlPrimaryKeyConstraintExtractor,
    SqlUniqueConstraintExtractor,
)

_NS = DAC_NAMESPACE


def _ns(tag: str) -> str:
    return f"{{{_NS}}}{tag}"


# --- XML fixture builders ---


def _add_defining_table(elem: Element, table_name: str) -> None:
    """Add a DefiningTable relationship to an element."""
    rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "DefiningTable"})
    entry = SubElement(rel, _ns("Entry"))
    SubElement(entry, _ns("References"), attrib={"Name": table_name})


def _add_column_spec(
    parent: Element,
    column_ref: str,
    *,
    is_descending: bool = False,
) -> None:
    """Add a SqlIndexedColumnSpecification to the ColumnSpecifications relationship."""
    # Find or create the ColumnSpecifications relationship
    col_specs_rel = None
    for rel in parent.findall(_ns("Relationship")):
        if rel.get("Name") == "ColumnSpecifications":
            col_specs_rel = rel
            break
    if col_specs_rel is None:
        col_specs_rel = SubElement(
            parent, _ns("Relationship"), attrib={"Name": "ColumnSpecifications"}
        )

    entry = SubElement(col_specs_rel, _ns("Entry"))
    spec = SubElement(
        entry,
        _ns("Element"),
        attrib={"Type": "SqlIndexedColumnSpecification"},
    )

    if is_descending:
        SubElement(
            spec, _ns("Property"), attrib={"Name": "IsDescending", "Value": "True"}
        )

    col_rel = SubElement(spec, _ns("Relationship"), attrib={"Name": "Column"})
    col_entry = SubElement(col_rel, _ns("Entry"))
    SubElement(col_entry, _ns("References"), attrib={"Name": column_ref})


def _add_filegroup(elem: Element, filegroup_name: str) -> None:
    """Add a Filegroup relationship to an element."""
    rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "Filegroup"})
    entry = SubElement(rel, _ns("Entry"))
    SubElement(entry, _ns("References"), attrib={"Name": filegroup_name})


def _build_pk(
    name: str = "[Application].[PK_Countries]",
    table_name: str = "[Application].[Countries]",
) -> Element:
    """Build a minimal SqlPrimaryKeyConstraint element."""
    pk = Element(
        _ns("Element"),
        attrib={"Type": "SqlPrimaryKeyConstraint", "Name": name},
    )
    _add_defining_table(pk, table_name)
    return pk


def _build_unique(
    name: str = "[dbo].[UQ_Email]",
    table_name: str = "[dbo].[Users]",
) -> Element:
    """Build a minimal SqlUniqueConstraint element."""
    uc = Element(
        _ns("Element"),
        attrib={"Type": "SqlUniqueConstraint", "Name": name},
    )
    _add_defining_table(uc, table_name)
    return uc


def _build_fk(
    name: str = "[Sales].[FK_Orders_Customers]",
) -> Element:
    """Build a SqlForeignKeyConstraint element shell (no relationships yet)."""
    return Element(
        _ns("Element"),
        attrib={"Type": "SqlForeignKeyConstraint", "Name": name},
    )


def _add_fk_relationships(
    fk_elem: Element,
    defining_table: str,
    foreign_table: str,
    columns: list[str],
    foreign_columns: list[str],
) -> None:
    """Add all required relationships to a FK element."""
    _add_defining_table(fk_elem, defining_table)

    # ForeignTable
    ft_rel = SubElement(fk_elem, _ns("Relationship"), attrib={"Name": "ForeignTable"})
    ft_entry = SubElement(ft_rel, _ns("Entry"))
    SubElement(ft_entry, _ns("References"), attrib={"Name": foreign_table})

    # Columns
    cols_rel = SubElement(fk_elem, _ns("Relationship"), attrib={"Name": "Columns"})
    for col in columns:
        entry = SubElement(cols_rel, _ns("Entry"))
        SubElement(entry, _ns("References"), attrib={"Name": col})

    # ForeignColumns
    fcols_rel = SubElement(
        fk_elem, _ns("Relationship"), attrib={"Name": "ForeignColumns"}
    )
    for col in foreign_columns:
        entry = SubElement(fcols_rel, _ns("Entry"))
        SubElement(entry, _ns("References"), attrib={"Name": col})


# --- extract_indexed_columns tests ---


class TestExtractIndexedColumns:
    """Unit tests for the shared extract_indexed_columns helper."""

    def test_ascending_by_default(self) -> None:
        elem = Element(_ns("Element"))
        _add_column_spec(elem, "[dbo].[T].[Col1]")

        cols = extract_indexed_columns(elem)

        assert len(cols) == 1
        assert cols[0].column_ref.parts == ("dbo", "T", "Col1")
        assert cols[0].sort_order == SortOrder.ASCENDING

    def test_descending_when_specified(self) -> None:
        elem = Element(_ns("Element"))
        _add_column_spec(elem, "[dbo].[T].[Col1]", is_descending=True)

        cols = extract_indexed_columns(elem)

        assert len(cols) == 1
        assert cols[0].sort_order == SortOrder.DESCENDING

    def test_document_order_preserved(self) -> None:
        elem = Element(_ns("Element"))
        _add_column_spec(elem, "[dbo].[T].[A]")
        _add_column_spec(elem, "[dbo].[T].[B]", is_descending=True)
        _add_column_spec(elem, "[dbo].[T].[C]")

        cols = extract_indexed_columns(elem)

        assert len(cols) == 3
        assert cols[0].column_ref.parts == ("dbo", "T", "A")
        assert cols[1].column_ref.parts == ("dbo", "T", "B")
        assert cols[2].column_ref.parts == ("dbo", "T", "C")

    def test_empty_when_no_column_specs(self) -> None:
        elem = Element(_ns("Element"))

        cols = extract_indexed_columns(elem)

        assert cols == ()

    def test_skips_spec_with_no_column_ref(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        elem = Element(_ns("Element"))
        # Create a ColumnSpecifications with an entry that has no Column relationship
        cs_rel = SubElement(
            elem, _ns("Relationship"), attrib={"Name": "ColumnSpecifications"}
        )
        entry = SubElement(cs_rel, _ns("Entry"))
        SubElement(
            entry,
            _ns("Element"),
            attrib={"Type": "SqlIndexedColumnSpecification"},
        )

        with caplog.at_level(logging.WARNING):
            cols = extract_indexed_columns(elem)

        assert cols == ()
        assert "no Column reference" in caplog.text


# --- PrimaryKey extractor tests ---


class TestPrimaryKeyAC1:
    """AC1: PK with name, table, columns, ascending sort order."""

    def test_pk_extraction(self) -> None:
        pk_elem = _build_pk("[Application].[PK_Countries]", "[Application].[Countries]")
        _add_column_spec(pk_elem, "[Application].[Countries].[CountryID]")

        extractor = SqlPrimaryKeyConstraintExtractor()
        results = extractor.extract([pk_elem], None)

        assert len(results) == 1
        pk = results[0]
        assert pk.name.parts == ("Application", "PK_Countries")
        assert pk.defining_table.parts == ("Application", "Countries")
        assert len(pk.columns) == 1
        assert pk.columns[0].sort_order == SortOrder.ASCENDING


class TestPrimaryKeyAC8:
    """AC8: PK with Filegroup reference."""

    def test_pk_with_filegroup(self) -> None:
        pk_elem = _build_pk()
        _add_column_spec(pk_elem, "[Application].[Countries].[CountryID]")
        _add_filegroup(pk_elem, "[USERDATA]")

        extractor = SqlPrimaryKeyConstraintExtractor()
        results = extractor.extract([pk_elem], None)

        assert len(results) == 1
        pk = results[0]
        assert pk.filegroup is not None
        assert pk.filegroup.parts == ("USERDATA",)


class TestPrimaryKeyMissingFilegroup:
    """PK without filegroup — filegroup is None."""

    def test_no_filegroup(self) -> None:
        pk_elem = _build_pk()
        _add_column_spec(pk_elem, "[Application].[Countries].[CountryID]")

        extractor = SqlPrimaryKeyConstraintExtractor()
        results = extractor.extract([pk_elem], None)

        assert len(results) == 1
        assert results[0].filegroup is None


class TestPrimaryKeyNoName:
    """Graceful degradation: PK with no Name attribute is skipped."""

    def test_no_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        pk_elem = Element(
            _ns("Element"), attrib={"Type": "SqlPrimaryKeyConstraint"}
        )
        _add_defining_table(pk_elem, "[dbo].[T]")

        extractor = SqlPrimaryKeyConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([pk_elem], None)

        assert results == ()
        assert "no Name attribute" in caplog.text


class TestPrimaryKeyNoDefiningTable:
    """Graceful degradation: PK with no DefiningTable is skipped."""

    def test_no_defining_table_skipped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        pk_elem = Element(
            _ns("Element"),
            attrib={"Type": "SqlPrimaryKeyConstraint", "Name": "[dbo].[PK_T]"},
        )

        extractor = SqlPrimaryKeyConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([pk_elem], None)

        assert results == ()
        assert "no DefiningTable" in caplog.text


class TestPrimaryKeyMultipleElements:
    """Multiple PK elements are all extracted."""

    def test_multiple_pks(self) -> None:
        pk1 = _build_pk("[dbo].[PK_A]", "[dbo].[A]")
        _add_column_spec(pk1, "[dbo].[A].[Id]")
        pk2 = _build_pk("[dbo].[PK_B]", "[dbo].[B]")
        _add_column_spec(pk2, "[dbo].[B].[Id]")

        extractor = SqlPrimaryKeyConstraintExtractor()
        results = extractor.extract([pk1, pk2], None)

        assert len(results) == 2
        assert results[0].name.parts == ("dbo", "PK_A")
        assert results[1].name.parts == ("dbo", "PK_B")


# --- UniqueConstraint extractor tests ---


class TestUniqueConstraintMirrorsPK:
    """Unique constraint has same structure as PK — name, table, columns, filegroup."""

    def test_unique_constraint_extraction(self) -> None:
        uc_elem = _build_unique("[dbo].[UQ_Email]", "[dbo].[Users]")
        _add_column_spec(uc_elem, "[dbo].[Users].[Email]")
        _add_filegroup(uc_elem, "[PRIMARY]")

        extractor = SqlUniqueConstraintExtractor()
        results = extractor.extract([uc_elem], None)

        assert len(results) == 1
        uc = results[0]
        assert uc.name.parts == ("dbo", "UQ_Email")
        assert uc.defining_table.parts == ("dbo", "Users")
        assert len(uc.columns) == 1
        assert uc.columns[0].column_ref.parts == ("dbo", "Users", "Email")
        assert uc.filegroup is not None
        assert uc.filegroup.parts == ("PRIMARY",)


class TestUniqueConstraintNoFilegroup:
    """Unique constraint without filegroup — filegroup is None."""

    def test_no_filegroup(self) -> None:
        uc_elem = _build_unique()
        _add_column_spec(uc_elem, "[dbo].[Users].[Email]")

        extractor = SqlUniqueConstraintExtractor()
        results = extractor.extract([uc_elem], None)

        assert len(results) == 1
        assert results[0].filegroup is None


class TestUniqueConstraintNoName:
    """Graceful degradation: Unique constraint with no Name is skipped."""

    def test_no_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        uc_elem = Element(
            _ns("Element"), attrib={"Type": "SqlUniqueConstraint"}
        )
        _add_defining_table(uc_elem, "[dbo].[T]")

        extractor = SqlUniqueConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([uc_elem], None)

        assert results == ()
        assert "no Name attribute" in caplog.text


class TestUniqueConstraintNoDefiningTable:
    """Graceful degradation: Unique constraint with no DefiningTable is skipped."""

    def test_no_defining_table_skipped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        uc_elem = Element(
            _ns("Element"),
            attrib={"Type": "SqlUniqueConstraint", "Name": "[dbo].[UQ_X]"},
        )

        extractor = SqlUniqueConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([uc_elem], None)

        assert results == ()
        assert "no DefiningTable" in caplog.text


# --- ForeignKey extractor tests ---


class TestForeignKeyAC2:
    """AC2: Single-column FK with correct parts."""

    def test_single_column_fk(self) -> None:
        fk_elem = _build_fk("[Sales].[FK_Orders_Customers]")
        _add_fk_relationships(
            fk_elem,
            defining_table="[Sales].[Orders]",
            foreign_table="[Sales].[Customers]",
            columns=["[Sales].[Orders].[CustomerID]"],
            foreign_columns=["[Sales].[Customers].[CustomerID]"],
        )

        extractor = SqlForeignKeyConstraintExtractor()
        results = extractor.extract([fk_elem], None)

        assert len(results) == 1
        fk = results[0]
        assert fk.name.parts == ("Sales", "FK_Orders_Customers")
        assert fk.defining_table.parts == ("Sales", "Orders")
        assert fk.foreign_table.parts == ("Sales", "Customers")
        assert len(fk.columns) == 1
        assert fk.columns[0].parts == ("Sales", "Orders", "CustomerID")
        assert len(fk.foreign_columns) == 1
        assert fk.foreign_columns[0].parts == ("Sales", "Customers", "CustomerID")


class TestForeignKeyAC3:
    """AC3: Composite FK with 2+2 positionally aligned columns."""

    def test_composite_fk(self) -> None:
        fk_elem = _build_fk("[dbo].[FK_OrderDetails_Products]")
        _add_fk_relationships(
            fk_elem,
            defining_table="[dbo].[OrderDetails]",
            foreign_table="[dbo].[Products]",
            columns=[
                "[dbo].[OrderDetails].[ProductID]",
                "[dbo].[OrderDetails].[VariantID]",
            ],
            foreign_columns=[
                "[dbo].[Products].[ProductID]",
                "[dbo].[Products].[VariantID]",
            ],
        )

        extractor = SqlForeignKeyConstraintExtractor()
        results = extractor.extract([fk_elem], None)

        assert len(results) == 1
        fk = results[0]
        assert len(fk.columns) == 2
        assert len(fk.foreign_columns) == 2
        # Positional alignment
        assert fk.columns[0].parts == ("dbo", "OrderDetails", "ProductID")
        assert fk.foreign_columns[0].parts == ("dbo", "Products", "ProductID")
        assert fk.columns[1].parts == ("dbo", "OrderDetails", "VariantID")
        assert fk.foreign_columns[1].parts == ("dbo", "Products", "VariantID")


class TestForeignKeyNoName:
    """Graceful degradation: FK with no Name is skipped."""

    def test_no_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        fk_elem = Element(
            _ns("Element"), attrib={"Type": "SqlForeignKeyConstraint"}
        )

        extractor = SqlForeignKeyConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([fk_elem], None)

        assert results == ()
        assert "no Name attribute" in caplog.text


class TestForeignKeyNoDefiningTable:
    """Graceful degradation: FK with no DefiningTable is skipped."""

    def test_no_defining_table(self, caplog: pytest.LogCaptureFixture) -> None:
        fk_elem = _build_fk("[dbo].[FK_Test]")
        # Only add ForeignTable, not DefiningTable
        ft_rel = SubElement(
            fk_elem, _ns("Relationship"), attrib={"Name": "ForeignTable"}
        )
        entry = SubElement(ft_rel, _ns("Entry"))
        SubElement(entry, _ns("References"), attrib={"Name": "[dbo].[Other]"})

        extractor = SqlForeignKeyConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([fk_elem], None)

        assert results == ()
        assert "no DefiningTable" in caplog.text


class TestForeignKeyNoForeignTable:
    """Graceful degradation: FK with no ForeignTable is skipped."""

    def test_no_foreign_table(self, caplog: pytest.LogCaptureFixture) -> None:
        fk_elem = _build_fk("[dbo].[FK_Test]")
        _add_defining_table(fk_elem, "[dbo].[T]")

        extractor = SqlForeignKeyConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([fk_elem], None)

        assert results == ()
        assert "no ForeignTable" in caplog.text


class TestForeignKeyMultiple:
    """Multiple FK elements are all extracted."""

    def test_multiple_fks(self) -> None:
        fk1 = _build_fk("[dbo].[FK_A]")
        _add_fk_relationships(
            fk1,
            defining_table="[dbo].[A]",
            foreign_table="[dbo].[B]",
            columns=["[dbo].[A].[BId]"],
            foreign_columns=["[dbo].[B].[Id]"],
        )
        fk2 = _build_fk("[dbo].[FK_C]")
        _add_fk_relationships(
            fk2,
            defining_table="[dbo].[C]",
            foreign_table="[dbo].[D]",
            columns=["[dbo].[C].[DId]"],
            foreign_columns=["[dbo].[D].[Id]"],
        )

        extractor = SqlForeignKeyConstraintExtractor()
        results = extractor.extract([fk1, fk2], None)

        assert len(results) == 2
        assert results[0].name.parts == ("dbo", "FK_A")
        assert results[1].name.parts == ("dbo", "FK_C")


# --- XML fixture builders for Check/Default constraints ---


def _build_check(
    name: str = "[dbo].[CK_Quantity]",
    table_name: str = "[dbo].[OrderDetails]",
) -> Element:
    """Build a minimal SqlCheckConstraint element."""
    elem = Element(
        _ns("Element"),
        attrib={"Type": "SqlCheckConstraint", "Name": name},
    )
    _add_defining_table(elem, table_name)
    return elem


def _add_cdata_property(elem: Element, prop_name: str, text: str) -> None:
    """Add a CDATA property (with Value sub-element) to an element."""
    prop = SubElement(elem, _ns("Property"), attrib={"Name": prop_name})
    value = SubElement(prop, _ns("Value"))
    value.text = text


def _build_default(
    name: str = "[dbo].[DF_Status]",
    table_name: str = "[dbo].[Users]",
    for_column: str = "[dbo].[Users].[Status]",
) -> Element:
    """Build a minimal SqlDefaultConstraint element."""
    elem = Element(
        _ns("Element"),
        attrib={"Type": "SqlDefaultConstraint", "Name": name},
    )
    _add_defining_table(elem, table_name)
    # ForColumn relationship
    rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "ForColumn"})
    entry = SubElement(rel, _ns("Entry"))
    SubElement(entry, _ns("References"), attrib={"Name": for_column})
    return elem


# --- CheckConstraint extractor tests ---


class TestCheckConstraintAC4:
    """AC4: Check constraint with expression [Quantity] > 0."""

    def test_check_expression(self) -> None:
        cc_elem = _build_check("[dbo].[CK_Quantity]", "[dbo].[OrderDetails]")
        _add_cdata_property(cc_elem, "CheckExpressionScript", "[Quantity] > 0")

        extractor = SqlCheckConstraintExtractor()
        results = extractor.extract([cc_elem], None)

        assert len(results) == 1
        cc = results[0]
        assert cc.name.parts == ("dbo", "CK_Quantity")
        assert cc.defining_table.parts == ("dbo", "OrderDetails")
        assert cc.expression == "[Quantity] > 0"


class TestCheckConstraintEmptyCDATA:
    """Edge case: Check constraint with empty CDATA — expression is empty string."""

    def test_empty_cdata(self) -> None:
        cc_elem = _build_check()
        _add_cdata_property(cc_elem, "CheckExpressionScript", "")

        extractor = SqlCheckConstraintExtractor()
        results = extractor.extract([cc_elem], None)

        assert len(results) == 1
        assert results[0].expression == ""


class TestCheckConstraintMissingCDATA:
    """Edge case: Check constraint with no CheckExpressionScript — expression defaults to empty."""

    def test_missing_cdata(self) -> None:
        cc_elem = _build_check()

        extractor = SqlCheckConstraintExtractor()
        results = extractor.extract([cc_elem], None)

        assert len(results) == 1
        assert results[0].expression == ""


class TestCheckConstraintNoName:
    """Graceful degradation: Check constraint with no Name is skipped."""

    def test_no_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        cc_elem = Element(
            _ns("Element"), attrib={"Type": "SqlCheckConstraint"}
        )
        _add_defining_table(cc_elem, "[dbo].[T]")

        extractor = SqlCheckConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([cc_elem], None)

        assert results == ()
        assert "no Name attribute" in caplog.text


class TestCheckConstraintNoDefiningTable:
    """Graceful degradation: Check constraint with no DefiningTable is skipped."""

    def test_no_defining_table(self, caplog: pytest.LogCaptureFixture) -> None:
        cc_elem = Element(
            _ns("Element"),
            attrib={"Type": "SqlCheckConstraint", "Name": "[dbo].[CK_Test]"},
        )

        extractor = SqlCheckConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([cc_elem], None)

        assert results == ()
        assert "no DefiningTable" in caplog.text


class TestCheckConstraintMultiple:
    """Multiple check constraints are all extracted."""

    def test_multiple_checks(self) -> None:
        cc1 = _build_check("[dbo].[CK_A]", "[dbo].[T]")
        _add_cdata_property(cc1, "CheckExpressionScript", "[A] > 0")
        cc2 = _build_check("[dbo].[CK_B]", "[dbo].[T]")
        _add_cdata_property(cc2, "CheckExpressionScript", "[B] < 100")

        extractor = SqlCheckConstraintExtractor()
        results = extractor.extract([cc1, cc2], None)

        assert len(results) == 2
        assert results[0].expression == "[A] > 0"
        assert results[1].expression == "[B] < 100"


# --- DefaultConstraint extractor tests ---


class TestDefaultConstraintAC5:
    """AC5: Default constraint for column with expression 'Active'."""

    def test_default_expression(self) -> None:
        dc_elem = _build_default(
            "[dbo].[DF_Status]",
            "[dbo].[Users]",
            "[dbo].[Users].[Status]",
        )
        _add_cdata_property(dc_elem, "DefaultExpressionScript", "'Active'")

        extractor = SqlDefaultConstraintExtractor()
        results = extractor.extract([dc_elem], None)

        assert len(results) == 1
        dc = results[0]
        assert dc.name.parts == ("dbo", "DF_Status")
        assert dc.defining_table.parts == ("dbo", "Users")
        assert dc.for_column.parts == ("dbo", "Users", "Status")
        assert dc.expression == "'Active'"


class TestDefaultConstraintEmptyCDATA:
    """Edge case: Default constraint with empty CDATA — expression is empty string."""

    def test_empty_cdata(self) -> None:
        dc_elem = _build_default()
        _add_cdata_property(dc_elem, "DefaultExpressionScript", "")

        extractor = SqlDefaultConstraintExtractor()
        results = extractor.extract([dc_elem], None)

        assert len(results) == 1
        assert results[0].expression == ""


class TestDefaultConstraintMissingCDATA:
    """Edge case: Default constraint with no DefaultExpressionScript — expression defaults to empty."""

    def test_missing_cdata(self) -> None:
        dc_elem = _build_default()

        extractor = SqlDefaultConstraintExtractor()
        results = extractor.extract([dc_elem], None)

        assert len(results) == 1
        assert results[0].expression == ""


class TestDefaultConstraintNoName:
    """Graceful degradation: Default constraint with no Name is skipped."""

    def test_no_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        dc_elem = Element(
            _ns("Element"), attrib={"Type": "SqlDefaultConstraint"}
        )
        _add_defining_table(dc_elem, "[dbo].[T]")

        extractor = SqlDefaultConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([dc_elem], None)

        assert results == ()
        assert "no Name attribute" in caplog.text


class TestDefaultConstraintNoDefiningTable:
    """Graceful degradation: Default constraint with no DefiningTable is skipped."""

    def test_no_defining_table(self, caplog: pytest.LogCaptureFixture) -> None:
        dc_elem = Element(
            _ns("Element"),
            attrib={"Type": "SqlDefaultConstraint", "Name": "[dbo].[DF_Test]"},
        )

        extractor = SqlDefaultConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([dc_elem], None)

        assert results == ()
        assert "no DefiningTable" in caplog.text


class TestDefaultConstraintNoForColumn:
    """Graceful degradation: Default constraint with no ForColumn is skipped."""

    def test_no_for_column(self, caplog: pytest.LogCaptureFixture) -> None:
        dc_elem = Element(
            _ns("Element"),
            attrib={"Type": "SqlDefaultConstraint", "Name": "[dbo].[DF_Test]"},
        )
        _add_defining_table(dc_elem, "[dbo].[T]")

        extractor = SqlDefaultConstraintExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([dc_elem], None)

        assert results == ()
        assert "no ForColumn" in caplog.text


class TestDefaultConstraintMultiple:
    """Multiple default constraints are all extracted."""

    def test_multiple_defaults(self) -> None:
        dc1 = _build_default("[dbo].[DF_A]", "[dbo].[T]", "[dbo].[T].[A]")
        _add_cdata_property(dc1, "DefaultExpressionScript", "0")
        dc2 = _build_default("[dbo].[DF_B]", "[dbo].[T]", "[dbo].[T].[B]")
        _add_cdata_property(dc2, "DefaultExpressionScript", "'X'")

        extractor = SqlDefaultConstraintExtractor()
        results = extractor.extract([dc1, dc2], None)

        assert len(results) == 2
        assert results[0].expression == "0"
        assert results[1].expression == "'X'"
