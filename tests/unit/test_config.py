from pathlib import Path

import pytest

from job_crawler.config import ConfigError, CrawlConfig

VALID_AGENT = "job-warehouse-crawler/0.1 (+public-research; contact=data@example.org)"


def config(**overrides):
    values = {
        "output_dir": Path("data/raw"),
        "authorization_reference": "APPROVAL-1",
        "user_agent": VALID_AGENT,
    }
    values.update(overrides)
    return CrawlConfig(**values)


def test_live_access_requires_authorization_reference() -> None:
    with pytest.raises(ConfigError, match="authorization"):
        config(authorization_reference=None).validate()


@pytest.mark.parametrize("pages,details", [(3, 20), (2, 21), (0, 1)])
def test_sample_limits_are_hard_caps(pages: int, details: int) -> None:
    with pytest.raises(ConfigError):
        config(max_pages=pages, max_details=details).validate()


def test_full_snapshot_requires_distinct_confirmation() -> None:
    with pytest.raises(ConfigError, match="confirm-full"):
        config(mode="full-snapshot", max_pages=None, max_details=None).validate()
