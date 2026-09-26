from datetime import UTC, datetime
from pathlib import Path

import pytest

from job_crawler.cli import _config_from_args, build_parser, main
from job_crawler.config import DEFAULT_CAREERVIET_START_URL, ConfigError, CrawlConfig
from job_crawler.crawlers.careerviet import CareerVietCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.factory import create_fetcher

USER_AGENT = "job-warehouse-test/0.1 (contact=data@example.org)"


def owner_config(tmp_path: Path, **overrides: object) -> CrawlConfig:
    values: dict[str, object] = {
        "source": "careerviet",
        "start_url": DEFAULT_CAREERVIET_START_URL,
        "mode": "sample",
        "max_pages": 1,
        "max_details": 3,
        "fetcher": "http",
        "project_owner_public_test": True,
        "authorization_reference": None,
        "user_agent": USER_AGENT,
        "output_dir": tmp_path,
    }
    values.update(overrides)
    return CrawlConfig(**values)  # type: ignore[arg-type]


def test_cli_owner_flag_defaults_to_one_listing_and_three_details() -> None:
    args = build_parser().parse_args(
        ["crawl", "careerviet", "--project-owner-public-test", "--user-agent", USER_AGENT]
    )
    config = _config_from_args(args)
    config.validate()
    assert (config.max_pages, config.max_details) == (1, 3)
    assert config.authorization_reference is None
    assert config.project_owner_public_test


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_pages": 2},
        {"max_details": 4},
        {"mode": "medium"},
        {"mode": "pilot"},
        {"authorization_reference": "SOURCE-REFERENCE"},
        {"fetcher": "playwright"},
    ],
)
def test_owner_basis_rejects_scope_expansion_or_mixed_provenance(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    with pytest.raises(ConfigError):
        owner_config(tmp_path, **overrides).validate()


def test_owner_basis_is_persisted_without_source_reference(tmp_path: Path) -> None:
    config = owner_config(tmp_path)
    config.validate()
    with create_fetcher(config) as fetcher:
        storage, manifest, _snapshot = CrawlEngine(
            config, CareerVietCrawler(), fetcher
        )._new_storage(datetime(2026, 9, 26, tzinfo=UTC))
        try:
            assert manifest.access_basis == "project_owner_public_test"
            assert manifest.authorization_reference is None
            assert manifest.authorization_references == []
            assert storage.read_manifest().access_basis == "project_owner_public_test"
        finally:
            storage.close()


def test_cli_rejects_owner_sample_above_cap_before_fetcher(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden_fetcher(_config: CrawlConfig) -> None:
        pytest.fail("Fetcher must not be constructed")

    monkeypatch.setattr("job_crawler.cli.create_fetcher", forbidden_fetcher)
    result = main(
        [
            "crawl",
            "careerviet",
            "--project-owner-public-test",
            "--max-details",
            "4",
            "--user-agent",
            USER_AGENT,
        ]
    )
    assert result == 2
    assert "one listing and three details" in capsys.readouterr().err
