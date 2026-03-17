"""ParsedName model for bracket-quoted SQL object names."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedName:
    """Immutable representation of a bracket-quoted SQL object name.

    All object names from model.xml are in ``[Part1].[Part2].[Part3]...`` form.
    This model stores the decomposed parts alongside convenience accessors for
    common positions (schema, object, sub-object).
    """

    raw: str
    parts: tuple[str, ...]
    schema_name: str | None
    object_name: str | None
    sub_name: str | None
