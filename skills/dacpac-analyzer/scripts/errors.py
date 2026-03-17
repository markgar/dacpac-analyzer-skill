"""Typed exceptions for dacpac/bacpac processing.

All package-related errors inherit from PackageError so callers can
catch a broad category or a specific sub-type.
"""

from __future__ import annotations

from pathlib import Path


class PackageError(Exception):
    """Base exception for all package processing errors."""


class PackageFileNotFoundError(PackageError):
    """The specified package file does not exist on disk."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Package file not found: {path}")


class InvalidArchiveError(PackageError):
    """The file is not a valid ZIP archive."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Not a valid ZIP archive: {path}")


class MissingEntryError(PackageError):
    """A required entry is missing from the archive."""

    def __init__(self, path: Path, entry_name: str) -> None:
        self.path = path
        self.entry_name = entry_name
        super().__init__(f"Required entry '{entry_name}' missing from archive: {path}")
