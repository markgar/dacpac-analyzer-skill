"""Bracket-quoted name parser — the sole mechanism for decomposing
bracket-quoted SQL object names from model.xml.

No other module may split bracket-quoted strings directly.
"""

from __future__ import annotations

import re

from models.parsed_name import ParsedName

_BRACKET_PART = re.compile(r"\[([^\]]*)\]")


def parse_name(raw: str) -> ParsedName:
    """Parse a bracket-quoted name into a ``ParsedName``.

    Accepts strings such as ``[Schema].[Table].[Column]`` and returns
    a ``ParsedName`` with the individual parts stripped of brackets.

    Raises ``ValueError`` for inputs that contain no bracket-quoted parts.
    """
    parts = tuple(_BRACKET_PART.findall(raw))
    if not parts:
        raise ValueError(f"No bracket-quoted parts found in: {raw!r}")

    schema_name = parts[0] if len(parts) >= 2 else None
    object_name = parts[1] if len(parts) >= 2 else None
    sub_name = parts[2] if len(parts) >= 3 else None

    return ParsedName(
        raw=raw,
        parts=parts,
        schema_name=schema_name,
        object_name=object_name,
        sub_name=sub_name,
    )
