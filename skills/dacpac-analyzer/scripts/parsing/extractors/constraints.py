"""Extractors for constraint element types.

Covers SqlPrimaryKeyConstraint, SqlUniqueConstraint,
SqlForeignKeyConstraint, SqlCheckConstraint, and
SqlDefaultConstraint. All produce frozen domain models from
model.xml elements.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from xml.etree.ElementTree import Element

from interfaces.protocols import ElementExtractor
from models.domain import (
    CheckConstraint,
    DefaultConstraint,
    ForeignKey,
    PrimaryKey,
    UniqueConstraint,
)
from parsing.extractors.column_helpers import (
    extract_indexed_columns,
    extract_primary_key,
)
from parsing.name_parser import parse_name
from parsing.xml_helpers import (
    get_cdata_property,
    get_relationship_references,
)

logger = logging.getLogger(__name__)


class SqlPrimaryKeyConstraintExtractor(ElementExtractor):
    """Extract ``PrimaryKey`` domain models from ``SqlPrimaryKeyConstraint`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlPrimaryKeyConstraint"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[PrimaryKey, ...]:
        results: list[PrimaryKey] = []
        for element in elements:
            pk = extract_primary_key(element)
            if pk is not None:
                results.append(pk)
        return tuple(results)


class SqlUniqueConstraintExtractor(ElementExtractor):
    """Extract ``UniqueConstraint`` domain models from ``SqlUniqueConstraint`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlUniqueConstraint"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[UniqueConstraint, ...]:
        results: list[UniqueConstraint] = []
        for element in elements:
            uc = _extract_unique_constraint(element)
            if uc is not None:
                results.append(uc)
        return tuple(results)


class SqlForeignKeyConstraintExtractor(ElementExtractor):
    """Extract ``ForeignKey`` domain models from ``SqlForeignKeyConstraint`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlForeignKeyConstraint"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[ForeignKey, ...]:
        results: list[ForeignKey] = []
        for element in elements:
            fk = _extract_foreign_key(element)
            if fk is not None:
                results.append(fk)
        return tuple(results)


def _extract_unique_constraint(element: Element) -> UniqueConstraint | None:
    """Extract a single ``UniqueConstraint`` from a ``SqlUniqueConstraint`` element."""
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlUniqueConstraint element with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlUniqueConstraint with malformed Name: %r", name_attr
        )
        return None

    defining_refs = get_relationship_references(element, "DefiningTable")
    if not defining_refs:
        logger.warning(
            "SqlUniqueConstraint %r has no DefiningTable — skipping", name_attr
        )
        return None
    defining_table = defining_refs[0]

    columns = extract_indexed_columns(element)

    fg_refs = get_relationship_references(element, "Filegroup")
    filegroup = fg_refs[0] if fg_refs else None

    return UniqueConstraint(
        name=parsed_name,
        defining_table=defining_table,
        columns=columns,
        filegroup=filegroup,
    )


def _extract_foreign_key(element: Element) -> ForeignKey | None:
    """Extract a single ``ForeignKey`` from a ``SqlForeignKeyConstraint`` element."""
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning(
            "Skipping SqlForeignKeyConstraint element with no Name attribute"
        )
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlForeignKeyConstraint with malformed Name: %r", name_attr
        )
        return None

    defining_refs = get_relationship_references(element, "DefiningTable")
    if not defining_refs:
        logger.warning(
            "SqlForeignKeyConstraint %r has no DefiningTable — skipping", name_attr
        )
        return None
    defining_table = defining_refs[0]

    foreign_table_refs = get_relationship_references(element, "ForeignTable")
    if not foreign_table_refs:
        logger.warning(
            "SqlForeignKeyConstraint %r has no ForeignTable — skipping", name_attr
        )
        return None
    foreign_table = foreign_table_refs[0]

    columns = get_relationship_references(element, "Columns")
    foreign_columns = get_relationship_references(element, "ForeignColumns")

    return ForeignKey(
        name=parsed_name,
        defining_table=defining_table,
        foreign_table=foreign_table,
        columns=columns,
        foreign_columns=foreign_columns,
    )


class SqlCheckConstraintExtractor(ElementExtractor):
    """Extract ``CheckConstraint`` domain models from ``SqlCheckConstraint`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlCheckConstraint"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[CheckConstraint, ...]:
        results: list[CheckConstraint] = []
        for element in elements:
            cc = _extract_check_constraint(element)
            if cc is not None:
                results.append(cc)
        return tuple(results)


class SqlDefaultConstraintExtractor(ElementExtractor):
    """Extract ``DefaultConstraint`` domain models from ``SqlDefaultConstraint`` elements."""

    @property
    def element_type(self) -> str:
        return "SqlDefaultConstraint"

    def extract(
        self, elements: Sequence[Element], context: Any
    ) -> tuple[DefaultConstraint, ...]:
        results: list[DefaultConstraint] = []
        for element in elements:
            dc = _extract_default_constraint(element)
            if dc is not None:
                results.append(dc)
        return tuple(results)


def _extract_check_constraint(element: Element) -> CheckConstraint | None:
    """Extract a single ``CheckConstraint`` from a ``SqlCheckConstraint`` element."""
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlCheckConstraint element with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlCheckConstraint with malformed Name: %r", name_attr
        )
        return None

    defining_refs = get_relationship_references(element, "DefiningTable")
    if not defining_refs:
        logger.warning(
            "SqlCheckConstraint %r has no DefiningTable — skipping", name_attr
        )
        return None
    defining_table = defining_refs[0]

    cdata = get_cdata_property(element, "CheckExpressionScript")
    expression = cdata.text if cdata is not None else ""

    return CheckConstraint(
        name=parsed_name,
        defining_table=defining_table,
        expression=expression,
    )


def _extract_default_constraint(element: Element) -> DefaultConstraint | None:
    """Extract a single ``DefaultConstraint`` from a ``SqlDefaultConstraint`` element."""
    name_attr = element.get("Name")
    if name_attr is None:
        logger.warning("Skipping SqlDefaultConstraint element with no Name attribute")
        return None

    try:
        parsed_name = parse_name(name_attr)
    except ValueError:
        logger.warning(
            "Skipping SqlDefaultConstraint with malformed Name: %r", name_attr
        )
        return None

    defining_refs = get_relationship_references(element, "DefiningTable")
    if not defining_refs:
        logger.warning(
            "SqlDefaultConstraint %r has no DefiningTable — skipping", name_attr
        )
        return None
    defining_table = defining_refs[0]

    for_column_refs = get_relationship_references(element, "ForColumn")
    if not for_column_refs:
        logger.warning(
            "SqlDefaultConstraint %r has no ForColumn — skipping", name_attr
        )
        return None
    for_column = for_column_refs[0]

    cdata = get_cdata_property(element, "DefaultExpressionScript")
    expression = cdata.text if cdata is not None else ""

    return DefaultConstraint(
        name=parsed_name,
        defining_table=defining_table,
        for_column=for_column,
        expression=expression,
    )
