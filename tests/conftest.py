"""Shared pytest fixtures for Prompt Genius tests."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def adapters_dir(repo_root: Path) -> Path:
    return repo_root / "examples" / "adapters"


@pytest.fixture(scope="session")
def catalog_dir(repo_root: Path) -> Path:
    return repo_root / "catalog"


@pytest.fixture(scope="session")
def schemas_dir(repo_root: Path) -> Path:
    return repo_root / "schemas"
