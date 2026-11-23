import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIX / name).read_text())


@pytest.fixture
def fixture():
    return load_fixture
