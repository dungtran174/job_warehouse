from pathlib import Path

import pytest

from job_crawler import feasibility
from job_crawler.feasibility import SOURCES, discover_details, extract_source_job_id, run_probe
from job_crawler.fetchers.base import FetchError, FetchResponse

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/vietnamworks/listing_saved_excerpt.html"
JD_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/vietnamworks/listing_jd_excerpt.html"
LISTING_URL = "https://www.vietnamworks.com/tim-viec-lam/tim-tat-ca-viec-lam"


def test_saved_listing_excerpt_discovers_unique_ids_without_detail_records() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    assert discover_details(html, LISTING_URL, SOURCES["vietnamworks"]) == [
        (
            "2110370",
            "https://www.vietnamworks.com/"
            "ho-card-product-and-service-specialist-1790074314650868388-2110370-jv",
        ),
        (
            "2110338",
            "https://www.vietnamworks.com/"
            "chuyen-vien-dam-bao-chat-luong-lam-viec-trong-truong-dai-hoc-"
            "1790073643299763474-2110338-jv",
        ),
        (
            "2110348",
            "https://www.vietnamworks.com/truong-nhom-truyen-thong-an-cung-ba-tuyet-2110348-jv",
        ),
    ]


def test_new_jd_listing_excerpt_discovers_five_unique_ids() -> None:
    html = JD_FIXTURE.read_text(encoding="utf-8")
    details = discover_details(html, LISTING_URL, SOURCES["vietnamworks"])
    assert [job_id for job_id, _url in details] == [
        "2109839",
        "2107184",
        "2107466",
        "2105036",
        "2105080",
    ]
    assert details[0][1] == (
        "https://www.vietnamworks.com/strategic-planning-1790044179001307861-2109839-jd"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://www.vietnamworks.com/not-a-detail-2110998-jv-extra",
        "https://www.vietnamworks.com/not-a-detail-2110997-jv/related",
        "https://www.vietnamworks.com/not-a-detail-2110998-jd-extra",
        "https://www.vietnamworks.com/not-a-detail-2110997-jd/related",
        "https://unrelated.example/job-2110999-jv",
        LISTING_URL,
    ],
)
def test_vietnamworks_id_rejects_non_detail_urls(url: str) -> None:
    assert extract_source_job_id(SOURCES["vietnamworks"], url) is None


def test_probe_without_approval_stops_before_artifacts_or_network(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Choose an access basis"):
        run_probe("vietnamworks", output_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_probe_cli_without_approval_stops_before_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = feasibility.main(["--source", "vietnamworks", "--output-dir", str(tmp_path)])
    assert result == 2
    assert "Choose an access basis" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_owner_probe_rejects_direct_browser_before_network(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must start with HTTP"):
        run_probe(
            "vietnamworks",
            project_owner_public_test=True,
            fetcher_mode="playwright",
            output_dir=tmp_path,
        )


def test_probe_stops_on_http_403_without_browser_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested: list[str] = []

    class FakeHttpFetcher:
        def __init__(self, _config: object) -> None:
            pass

        def get(self, url: str) -> FetchResponse:
            requested.append(url)
            if url.endswith("/robots.txt"):
                return FetchResponse(
                    url=url,
                    text="User-agent: *\nAllow: /\n",
                    status_code=200,
                    headers={},
                    attempt=1,
                    duration_seconds=0.0,
                    fetcher="http",
                )
            raise FetchError(
                "Access stopped by HTTP 403",
                url=url,
                attempt=1,
                status_code=403,
                blocked=True,
            )

        def close(self) -> None:
            pass

    def forbidden_browser(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Browser fallback must not run after HTTP 403")

    monkeypatch.setattr(feasibility, "HttpFetcher", FakeHttpFetcher)
    monkeypatch.setattr(feasibility, "PlaywrightFetcher", forbidden_browser)
    report, _root = run_probe(
        "vietnamworks",
        project_owner_public_test=True,
        output_dir=tmp_path,
        fetcher_mode="auto",
    )
    assert requested == [
        "https://www.vietnamworks.com/robots.txt",
        LISTING_URL,
    ]
    assert report.status == "stopped"
    assert report.stop_reason == "access_blocked"
    assert report.access_basis == "project_owner_public_test"
    assert report.detail_attempts == 0
