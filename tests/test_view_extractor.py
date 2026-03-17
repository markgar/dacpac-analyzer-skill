"""Tests for SqlViewExtractor — Spec 09, AC 6."""

from __future__ import annotations

import logging

import pytest

from constants import DAC_NAMESPACE
from models.domain import View
from parsing.extractors.view import SqlViewExtractor
from parsing.model_parser import XmlModelParser
from parsing.registry import ExtractorRegistry

_ROOT_ATTRS = (
    f'xmlns="{DAC_NAMESPACE}" '
    'FileFormatVersion="1.2" '
    'SchemaVersion="2.9" '
    'DspName="Microsoft.Data.Tools.Schema.Sql.Sql130DatabaseSchemaProvider" '
    'CollationLcid="1033" '
    'CollationCaseSensitive="False"'
)


def _make_model_xml(
    *,
    root_attrs: str = _ROOT_ATTRS,
    elements_xml: str = "",
) -> bytes:
    """Build a minimal model.xml bytes payload."""
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f"<DataSchemaModel {root_attrs}>"
        f"<Model>{elements_xml}</Model>"
        f"</DataSchemaModel>"
    ).encode("utf-8")


def _make_computed_column(name: str) -> str:
    """Build a SqlComputedColumn inline element XML string."""
    return (
        f'<Element Type="SqlComputedColumn" Name="{name}">'
        f'<Property Name="ExpressionScript">'
        f"<Value><![CDATA[some_expr]]></Value>"
        f"</Property>"
        f"</Element>"
    )


def _make_view_element(
    name: str,
    schema: str,
    *,
    query_script: str | None = None,
    column_names: tuple[str, ...] = (),
) -> str:
    """Build a SqlView element XML string."""
    schema_rel = (
        f'<Relationship Name="Schema">'
        f"<Entry>"
        f'<References Name="{schema}" />'
        f"</Entry>"
        f"</Relationship>"
    )

    query_prop = ""
    if query_script is not None:
        query_prop = (
            f'<Property Name="QueryScript">'
            f"<Value><![CDATA[{query_script}]]></Value>"
            f"</Property>"
        )

    columns_rel = ""
    if column_names:
        entries = ""
        for col_name in column_names:
            entries += f"<Entry>{_make_computed_column(col_name)}</Entry>"
        columns_rel = f'<Relationship Name="Columns">{entries}</Relationship>'

    return (
        f'<Element Type="SqlView" Name="{name}">'
        f"{query_prop}"
        f"{schema_rel}"
        f"{columns_rel}"
        f"</Element>"
    )


class TestAC6ViewWithQueryScriptAndColumns:
    """AC 6: GIVEN SqlView with QueryScript containing 'SELECT * FROM [Sales].[Orders]'
    and 3 SqlComputedColumn children
    WHEN extracted
    THEN query_script is the SELECT statement and columns has 3 entries."""

    def test_full_view_extracted(self) -> None:
        elements_xml = _make_view_element(
            "[Sales].[OrdersSummary]",
            "[Sales]",
            query_script="SELECT * FROM [Sales].[Orders]",
            column_names=(
                "[Sales].[OrdersSummary].[OrderID]",
                "[Sales].[OrdersSummary].[CustomerName]",
                "[Sales].[OrdersSummary].[Total]",
            ),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlViewExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.views) == 1
        view = model.views[0]
        assert view.name.parts == ("Sales", "OrdersSummary")
        assert view.schema_ref.parts == ("Sales",)
        assert view.query_script == "SELECT * FROM [Sales].[Orders]"
        assert len(view.columns) == 3
        assert view.columns[0].name.parts == ("Sales", "OrdersSummary", "OrderID")
        assert view.columns[1].name.parts == ("Sales", "OrdersSummary", "CustomerName")
        assert view.columns[2].name.parts == ("Sales", "OrdersSummary", "Total")
        # Computed columns
        assert all(col.is_computed for col in view.columns)


class TestViewEmptyQueryScript:
    """Edge case: SqlView with no QueryScript property."""

    def test_empty_query_script(self) -> None:
        elements_xml = _make_view_element(
            "[dbo].[EmptyView]",
            "[dbo]",
            query_script=None,
            column_names=(),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlViewExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.views) == 1
        view = model.views[0]
        assert view.query_script == ""


class TestViewNoColumns:
    """Edge case: SqlView with query script but no columns."""

    def test_no_columns(self) -> None:
        elements_xml = _make_view_element(
            "[dbo].[SimpleView]",
            "[dbo]",
            query_script="SELECT 1",
            column_names=(),
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlViewExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.views) == 1
        view = model.views[0]
        assert view.query_script == "SELECT 1"
        assert len(view.columns) == 0


class TestViewMissingName:
    """Edge case: SqlView with no Name attribute is skipped."""

    def test_missing_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = '<Element Type="SqlView" />'
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlViewExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.view"):
            model = parser.parse(content).database_model

        assert len(model.views) == 0
        assert any("no Name" in msg for msg in caplog.messages)


class TestViewMissingSchema:
    """Edge case: SqlView with no Schema relationship is skipped."""

    def test_missing_schema_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlView" Name="[dbo].[MyView]">'
            '<Property Name="QueryScript">'
            "<Value><![CDATA[SELECT 1]]></Value>"
            "</Property>"
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlViewExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.view"):
            model = parser.parse(content).database_model

        assert len(model.views) == 0
        assert any("no Schema" in msg for msg in caplog.messages)


class TestViewMalformedName:
    """Edge case: SqlView with malformed Name is skipped."""

    def test_malformed_name_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        elements_xml = (
            '<Element Type="SqlView" Name="not-a-valid-name">'
            '<Relationship Name="Schema">'
            "<Entry>"
            '<References Name="[dbo]" />'
            "</Entry>"
            "</Relationship>"
            "</Element>"
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlViewExtractor())
        parser = XmlModelParser(registry)

        with caplog.at_level(logging.WARNING, logger="parsing.extractors.view"):
            model = parser.parse(content).database_model

        assert len(model.views) == 0
        assert any("malformed Name" in msg for msg in caplog.messages)


class TestMultipleViews:
    """Multiple views are all extracted."""

    def test_multiple_views(self) -> None:
        elements_xml = (
            _make_view_element(
                "[dbo].[View1]", "[dbo]",
                query_script="SELECT 1",
                column_names=("[dbo].[View1].[Col1]",),
            )
            + _make_view_element(
                "[Sales].[View2]", "[Sales]",
                query_script="SELECT 2",
                column_names=(
                    "[Sales].[View2].[ColA]",
                    "[Sales].[View2].[ColB]",
                ),
            )
        )
        content = _make_model_xml(elements_xml=elements_xml)

        registry = ExtractorRegistry()
        registry.register(SqlViewExtractor())
        parser = XmlModelParser(registry)

        model = parser.parse(content).database_model

        assert len(model.views) == 2
        assert model.views[0].name.parts == ("dbo", "View1")
        assert len(model.views[0].columns) == 1
        assert model.views[1].name.parts == ("Sales", "View2")
        assert len(model.views[1].columns) == 2


class TestExtractorElementType:
    """Verify extractor reports the correct element type."""

    def test_element_type(self) -> None:
        extractor = SqlViewExtractor()
        assert extractor.element_type == "SqlView"
