"""Shared pytest configuration for dacpac-analyzer tests."""

import sys
from pathlib import Path

# Add the scripts directory to sys.path so tests can import modules directly
_scripts_dir = Path(__file__).resolve().parent.parent / "skills" / "dacpac-analyzer" / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))
