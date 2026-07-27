import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def lmnt_html() -> str:
    return (FIXTURES / "lmnt_recharge.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def source_url() -> str:
    return "https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack"
