from pathlib import Path

import pytest


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "topcv"


@pytest.fixture
def read_fixture(fixture_dir: Path):
    def _read(name: str) -> str:
        return (fixture_dir / name).read_text(encoding="utf-8")

    return _read


@pytest.fixture
def read_source_fixture():
    root = Path(__file__).parent / "fixtures"

    def _read(source: str, name: str) -> str:
        return (root / source / name).read_text(encoding="utf-8")

    return _read
