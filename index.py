"""Vercel entry when the API project root is the repository, not backend/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from support_api import app  # noqa: E402
