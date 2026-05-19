"""
Stage 1: Intake.

Loads the user's seed keyword and intake answers into a SeedInput object.
In Colab/Streamlit this would be wrapped in a UI; here it's just JSON loading
so the engine can be tested headlessly.
"""

import json
from pathlib import Path

from models import SeedInput


def load_intake_from_json(path: str | Path) -> SeedInput:
    """Load a SeedInput from a JSON file. Used for fixture-based testing."""
    with open(path) as f:
        data = json.load(f)
    return SeedInput.model_validate(data)


def load_intake_from_dict(data: dict) -> SeedInput:
    """Load a SeedInput from a dict. Used by the UI layer."""
    return SeedInput.model_validate(data)
