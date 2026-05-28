"""Shared pytest fixtures + sys.path setup.

Ensures `from backend.X import Y` works when pytest runs from the backend/ dir
or project root.
"""
import sys
from pathlib import Path

# Add project root (the parent of `backend/`) to sys.path so `import backend`
# resolves to this package directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
