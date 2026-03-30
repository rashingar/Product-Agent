from __future__ import annotations

from pathlib import Path

import pytest

_TESTS_ROOT = Path(__file__).resolve().parent
_FIXTURES_ROOT = _TESTS_ROOT / "fixtures"
_PROVIDERS_FIXTURES_ROOT = _FIXTURES_ROOT / "providers"
_REPO_ROOT = _TESTS_ROOT.parents[2]


@pytest.fixture(scope="session")
def tests_root() -> Path:
    return _TESTS_ROOT


@pytest.fixture(scope="session")
def fixtures_root() -> Path:
    return _FIXTURES_ROOT


@pytest.fixture(scope="session")
def providers_fixtures_root() -> Path:
    return _PROVIDERS_FIXTURES_ROOT


@pytest.fixture(scope="session")
def skroutz_provider_fixtures_root(providers_fixtures_root: Path) -> Path:
    return providers_fixtures_root / "skroutz"


@pytest.fixture(scope="session")
def electronet_provider_fixtures_root(providers_fixtures_root: Path) -> Path:
    return providers_fixtures_root / "electronet"


@pytest.fixture(scope="session")
def manufacturer_tefal_provider_fixtures_root(providers_fixtures_root: Path) -> Path:
    return providers_fixtures_root / "manufacturer_tefal"


@pytest.fixture(scope="session")
def pipeline_run_fixtures_root(fixtures_root: Path) -> Path:
    return fixtures_root / "pipeline_runs"


@pytest.fixture(scope="session")
def golden_outputs_root(fixtures_root: Path) -> Path:
    return fixtures_root / "golden_outputs"


@pytest.fixture(scope="session")
def skroutz_fixtures_root(skroutz_provider_fixtures_root: Path) -> Path:
    return skroutz_provider_fixtures_root


@pytest.fixture(scope="session")
def products_root() -> Path:
    return _REPO_ROOT / "products"
