import gzip
import json
import runpy
from pathlib import Path

import httpx
import pytest
import respx

from job_crawler.cli import _config_from_args, build_parser
from job_crawler.config import DEFAULT_TOPCV_START_URL, ConfigError

capture = runpy.run_path(str(Path(__file__).parents[2] / "scripts/public_source_probe.py"))[
    "capture"
]
USER_AGENT = "job-warehouse-test/0.1 (public research; contact=data@example.org)"


def test_topcv_owner_sample_does_not_require_source_authorization() -> None:
    args = build_parser().parse_args(
        ["crawl", "topcv", "--project-owner-public-test", "--user-agent", USER_AGENT]
    )
    config = _config_from_args(args)
    config.validate()
    assert config.source == "topcv"
    assert config.start_url == DEFAULT_TOPCV_START_URL
    assert config.project_owner_public_test
    assert config.authorization_reference is None
    assert (config.max_pages, config.max_details) == (1, 3)


@pytest.mark.parametrize(
    "extra",
    [
        ["--max-pages", "2"],
        ["--max-details", "4"],
        ["--authorization-reference", "NOT-OWNER-APPROVAL"],
        ["--mode", "pilot", "--max-details", "20"],
    ],
)
def test_topcv_probe_cannot_expand_or_claim_source_permission(extra: list[str]) -> None:
    args = build_parser().parse_args(
        ["crawl", "topcv", "--project-owner-public-test", "--user-agent", USER_AGENT, *extra]
    )
    with pytest.raises(ConfigError):
        _config_from_args(args).validate()


@respx.mock
@pytest.mark.parametrize(
    "status,body",
    [
        (401, "Login required"),
        (403, "Forbidden"),
        (429, "Too many requests"),
        (200, "<title>Just a moment</title>cf-chl-test"),
    ],
)
def test_topcv_probe_saves_denial_without_retry(tmp_path: Path, status: int, body: str) -> None:
    route = respx.get(DEFAULT_TOPCV_START_URL).mock(return_value=httpx.Response(status, text=body))
    with pytest.raises(RuntimeError, match="STOP source"):
        capture(tmp_path, "listing", DEFAULT_TOPCV_START_URL, delay=0)
    assert route.call_count == 1
    assert len(respx.calls) == 1
    metadata = json.loads((tmp_path / "listing.json").read_text())
    assert metadata["status"] == status
    assert metadata["blocked"]
    assert metadata["final_url"] == DEFAULT_TOPCV_START_URL
    assert gzip.decompress((tmp_path / "listing.hop-0.body.gz").read_bytes()).decode() == body
