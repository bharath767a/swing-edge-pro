"""Pytest configuration — adds project root to sys.path."""
import sys
from pathlib import Path

# Add project root to sys.path so `backend` package is importable
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
