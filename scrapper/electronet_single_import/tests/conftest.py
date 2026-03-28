from __future__ import annotations

from pathlib import Path

import pytest

_TESTS_ROOT = Path(__file__).resolve().parent
_FIXTURES_ROOT = _TESTS_ROOT / "fixtures"
_REPO_ROOT = _TESTS_ROOT.parents[2]


@pytest.fixture(scope="session")
def tests_root() -> Path:
    return _TESTS_ROOT


@pytest.fixture(scope="session")
def fixtures_root() -> Path:
    return _FIXTURES_ROOT


@pytest.fixture(scope="session")
def skroutz_fixtures_root(fixtures_root: Path) -> Path:
    return fixtures_root / "skroutz"


@pytest.fixture(scope="session")
def products_root() -> Path:
    return _REPO_ROOT / "products"
