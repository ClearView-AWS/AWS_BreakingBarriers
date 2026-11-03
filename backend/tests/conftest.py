"""Let `pytest backend/tests` run from the repo root as well as from backend/."""

import sys
from pathlib import Path

BACKEND = str(Path(__file__).resolve().parents[1])
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)
