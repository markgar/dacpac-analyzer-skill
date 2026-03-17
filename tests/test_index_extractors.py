"""Tests for index extractors (SqlIndex, SqlColumnStoreIndex).

Maps to Spec 07 acceptance criteria for index extraction.
"""

from __future__ import annotations

import logging
from xml.etree.ElementTree import Element, SubElement

import pytest

from constants import DAC_NAMESPACE
from models.enums import SortOrder
from parsing.extractors.indexes import (
    SqlColumnStoreIndexExtractor,
    SqlIndexExtractor,
)

_NS = DAC_NAMESPACE


def _ns(tag: str) -> str:
    return f"{{{_NS}}}{tag}"


# --- XML fixture builders ---


def _add_indexed_object(elem: Element, object_name: str) -> None:
    """Add an IndexedObject relationship to an element."""
    rel = SubElement(elem, _ns("Relationship"), attrib={"Name": "IndexedObject"})
    entry = SubElement(rel, _ns("Entry"))
    SubElement(entry, _ns("References"), attrib={"Name": object_name})


def _add_column_spec(
    parent: Element,
    column_ref: str,
    *,
    is_descending: bool = False,
) -> None:
    """Add a SqlIndexedColumnSpecification to the ColumnSpecifications relationship."""
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


def _build_index(
    name: str = "[dbo].[IX_Orders_Date]",
    indexed_object: str = "[dbo].[Orders]",
) -> Element:
    """Build a minimal SqlIndex element."""
    idx = Element(
        _ns("Element"),
        attrib={"Type": "SqlIndex", "Name": name},
    )
    _add_indexed_object(idx, indexed_object)
    return idx


def _build_columnstore_index(
    name: str = "[Warehouse].[NCCX_ColdRoomTemperatures]",
    indexed_object: str = "[Warehouse].[ColdRoomTemperatures]",
) -> Element:
    """Build a minimal SqlColumnStoreIndex element."""
    idx = Element(
        _ns("Element"),
        attrib={"Type": "SqlColumnStoreIndex", "Name": name},
    )
    _add_indexed_object(idx, indexed_object)
    return idx


# --- SqlIndex extractor tests ---


class TestIndexAC6:
    """AC6: Index with two columns — first ASC, second DESC."""

    def test_two_columns_sort_order(self) -> None:
        idx_elem = _build_index("[dbo].[IX_Orders_Multi]", "[dbo].[Orders]")
        _add_column_spec(idx_elem, "[dbo].[Orders].[OrderDate]")
        _add_column_spec(
            idx_elem, "[dbo].[Orders].[CustomerID]", is_descending=True
        )

        extractor = SqlIndexExtractor()
        results = extractor.extract([idx_elem], None)

        assert len(results) == 1
        idx = results[0]
        assert idx.name.parts == ("dbo", "IX_Orders_Multi")
        assert idx.indexed_object.parts == ("dbo", "Orders")
        assert len(idx.columns) == 2
        assert idx.columns[0].sort_order == SortOrder.ASCENDING
        assert idx.columns[0].column_ref.parts == ("dbo", "Orders", "OrderDate")
        assert idx.columns[1].sort_order == SortOrder.DESCENDING
        assert idx.columns[1].column_ref.parts == ("dbo", "Orders", "CustomerID")
        assert idx.is_columnstore is False


class TestIndexWithFilegroup:
    """Index with a Filegroup reference."""

    def test_filegroup(self) -> None:
        idx_elem = _build_index()
        _add_column_spec(idx_elem, "[dbo].[Orders].[OrderDate]")
        _add_filegroup(idx_elem, "[USERDATA]")

        extractor = SqlIndexExtractor()
        results = extractor.extract([idx_elem], None)

        assert len(results) == 1
        assert results[0].filegroup is not None
        assert results[0].filegroup.parts == ("USERDATA",)


class TestIndexNoFilegroup:
    """Index without filegroup — filegroup is None."""

    def test_no_filegroup(self) -> None:
        idx_elem = _build_index()
        _add_column_spec(idx_elem, "[dbo].[Orders].[OrderDate]")

        extractor = SqlIndexExtractor()
        results = extractor.extract([idx_elem], None)

        assert len(results) == 1
        assert results[0].filegroup is None


class TestIndexNoName:
    """Graceful degradation: Index with no Name attribute is skipped."""

    def test_no_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        idx_elem = Element(_ns("Element"), attrib={"Type": "SqlIndex"})
        _add_indexed_object(idx_elem, "[dbo].[T]")

        extractor = SqlIndexExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([idx_elem], None)

        assert results == ()
        assert "no Name attribute" in caplog.text


class TestIndexNoIndexedObject:
    """Graceful degradation: Index with no IndexedObject is skipped."""

    def test_no_indexed_object(self, caplog: pytest.LogCaptureFixture) -> None:
        idx_elem = Element(
            _ns("Element"),
            attrib={"Type": "SqlIndex", "Name": "[dbo].[IX_Test]"},
        )

        extractor = SqlIndexExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([idx_elem], None)

        assert results == ()
        assert "no IndexedObject" in caplog.text


class TestIndexMultiple:
    """Multiple index elements are all extracted."""

    def test_multiple_indexes(self) -> None:
        idx1 = _build_index("[dbo].[IX_A]", "[dbo].[A]")
        _add_column_spec(idx1, "[dbo].[A].[Col1]")
        idx2 = _build_index("[dbo].[IX_B]", "[dbo].[B]")
        _add_column_spec(idx2, "[dbo].[B].[Col1]")

        extractor = SqlIndexExtractor()
        results = extractor.extract([idx1, idx2], None)

        assert len(results) == 2
        assert results[0].name.parts == ("dbo", "IX_A")
        assert results[1].name.parts == ("dbo", "IX_B")
        assert all(not r.is_columnstore for r in results)


class TestIndexIsNotColumnstore:
    """SqlIndex always produces is_columnstore=False."""

    def test_not_columnstore(self) -> None:
        idx_elem = _build_index()
        _add_column_spec(idx_elem, "[dbo].[Orders].[OrderDate]")

        extractor = SqlIndexExtractor()
        results = extractor.extract([idx_elem], None)

        assert len(results) == 1
        assert results[0].is_columnstore is False


# --- SqlColumnStoreIndex extractor tests ---


class TestColumnStoreIndexAC7:
    """AC7: Columnstore index has is_columnstore=True."""

    def test_columnstore_flag(self) -> None:
        idx_elem = _build_columnstore_index(
            "[Warehouse].[NCCX_ColdRoomTemperatures]",
            "[Warehouse].[ColdRoomTemperatures]",
        )

        extractor = SqlColumnStoreIndexExtractor()
        results = extractor.extract([idx_elem], None)

        assert len(results) == 1
        idx = results[0]
        assert idx.name.parts == ("Warehouse", "NCCX_ColdRoomTemperatures")
        assert idx.indexed_object.parts == ("Warehouse", "ColdRoomTemperatures")
        assert idx.is_columnstore is True


class TestColumnStoreIndexEmptyColumns:
    """Clustered columnstore index with no column specifications."""

    def test_empty_columns(self) -> None:
        idx_elem = _build_columnstore_index()

        extractor = SqlColumnStoreIndexExtractor()
        results = extractor.extract([idx_elem], None)

        assert len(results) == 1
        assert results[0].columns == ()
        assert results[0].is_columnstore is True


class TestColumnStoreIndexWithColumns:
    """Non-clustered columnstore index with explicit column list."""

    def test_with_columns(self) -> None:
        idx_elem = _build_columnstore_index(
            "[dbo].[NCCX_Sales]", "[dbo].[Sales]"
        )
        _add_column_spec(idx_elem, "[dbo].[Sales].[Amount]")
        _add_column_spec(idx_elem, "[dbo].[Sales].[Date]")

        extractor = SqlColumnStoreIndexExtractor()
        results = extractor.extract([idx_elem], None)

        assert len(results) == 1
        idx = results[0]
        assert len(idx.columns) == 2
        assert idx.columns[0].column_ref.parts == ("dbo", "Sales", "Amount")
        assert idx.columns[1].column_ref.parts == ("dbo", "Sales", "Date")


class TestColumnStoreIndexWithFilegroup:
    """Columnstore index with filegroup reference."""

    def test_filegroup(self) -> None:
        idx_elem = _build_columnstore_index()
        _add_filegroup(idx_elem, "[COLUMNSTORE_DATA]")

        extractor = SqlColumnStoreIndexExtractor()
        results = extractor.extract([idx_elem], None)

        assert len(results) == 1
        assert results[0].filegroup is not None
        assert results[0].filegroup.parts == ("COLUMNSTORE_DATA",)


class TestColumnStoreIndexNoName:
    """Graceful degradation: Columnstore index with no Name is skipped."""

    def test_no_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        idx_elem = Element(
            _ns("Element"), attrib={"Type": "SqlColumnStoreIndex"}
        )
        _add_indexed_object(idx_elem, "[dbo].[T]")

        extractor = SqlColumnStoreIndexExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([idx_elem], None)

        assert results == ()
        assert "no Name attribute" in caplog.text


class TestColumnStoreIndexNoIndexedObject:
    """Graceful degradation: Columnstore index with no IndexedObject is skipped."""

    def test_no_indexed_object(self, caplog: pytest.LogCaptureFixture) -> None:
        idx_elem = Element(
            _ns("Element"),
            attrib={
                "Type": "SqlColumnStoreIndex",
                "Name": "[dbo].[NCCX_Test]",
            },
        )

        extractor = SqlColumnStoreIndexExtractor()
        with caplog.at_level(logging.WARNING):
            results = extractor.extract([idx_elem], None)

        assert results == ()
        assert "no IndexedObject" in caplog.text


class TestColumnStoreIndexMultiple:
    """Multiple columnstore index elements are all extracted."""

    def test_multiple_columnstore(self) -> None:
        idx1 = _build_columnstore_index("[dbo].[NCCX_A]", "[dbo].[A]")
        idx2 = _build_columnstore_index("[dbo].[CCX_B]", "[dbo].[B]")

        extractor = SqlColumnStoreIndexExtractor()
        results = extractor.extract([idx1, idx2], None)

        assert len(results) == 2
        assert results[0].name.parts == ("dbo", "NCCX_A")
        assert results[1].name.parts == ("dbo", "CCX_B")
        assert all(r.is_columnstore for r in results)
