import gzip
import hashlib
import json
import runpy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import Error as PlaywrightError
from selectolax.parser import HTMLParser

from job_crawler.cli import _config_from_args, build_parser
from job_crawler.config import ConfigError, CrawlConfig
from job_crawler.crawlers.vieclam24h import Vieclam24hCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.base import FetchError, FetcherState, FetchResponse
from job_crawler.fetchers.vieclam24h import ROBOTS, Vieclam24hBrowserFetcher
from job_crawler.parsers.vieclam24h import START_URL, job_url, parse_detail, parse_listing

ROOT = Path(__file__).parents[1] / "fixtures/vieclam24h"


def config(tmp_path, **changes):
    values = dict(
        source="vieclam24h",
        mode="bounded",
        start_url=START_URL,
        output_dir=tmp_path,
        project_owner_public_test=True,
        fetcher="playwright",
        headed=True,
        max_pages=1,
        max_details=2,
        delay_min_seconds=10,
        delay_max_seconds=15,
        max_retries=0,
        save_html=True,
        require_complete_content=True,
        save_screenshot_on_error=True,
    )
    values.update(changes)
    return CrawlConfig(**values)


def detail(i):
    return (ROOT / f"detail_{i}.html").read_text()


def record(html, job=None):
    if job is None:
        url = HTMLParser(html).css_first('link[rel="canonical"]').attributes["href"]
        job = next(
            j
            for j in parse_listing((ROOT / "listing.html").read_text(), START_URL).jobs
            if j.source_job_id == job_url(url)[0]
        )
    now = datetime.now(UTC)
    return parse_detail(
        html,
        job,
        crawled_at=now,
        snapshot_date=now.date(),
        batch_id="offline",
        source_reported_total=None,
        raw_html_path=None,
    )


def test_main_listing_excludes_suggestions_and_keeps_page_two():
    page = parse_listing((ROOT / "listing.html").read_text(), START_URL)
    assert [j.source_job_id for j in page.jobs] == ["200941421", "200944169"]
    assert page.next_url == START_URL + "?page=2"
    assert all("?" not in j.canonical_url for j in page.jobs)


def test_no_partial_main_or_repeated_page_is_accepted():
    html = (ROOT / "listing.html").read_text()
    with pytest.raises(ValueError, match="missing/incomplete"):
        parse_listing(html.replace('data-ojb="0201_1_1"', 'data-ojb="suggested"'), START_URL)
    with pytest.raises(ValueError, match="page mismatch"):
        parse_listing(html, START_URL + "?page=2")


def test_page_two_tracking_prefix_is_not_page_one_only():
    html = (ROOT / "listing.html").read_text()
    html = html.replace('"current":1', '"current":2').replace("0201_1_", "0201_2_")
    page = parse_listing(html, START_URL + "?page=2")
    assert len(page.jobs) == 2 and page.next_url is None


@pytest.mark.parametrize("i", [1, 2])
def test_full_detail_not_listing_or_paperwork_and_employer_id_not_job_id(i):
    r = record(detail(i))
    assert r.company_id != r.source_job_id
    assert r.company_name and r.job_description and r.candidate_requirements
    assert "Application paperwork" not in r.candidate_requirements
    assert r.salary_raw and r.location_raw
    assert r.posted_at_raw == ("18/09/2026" if i == 1 else "22/09/2026")
    assert r.content_hash and r.candidate_requirements.endswith(("Final criterion.", "Last skill."))


def test_missing_fields_stay_null_and_updated_not_posted():
    from job_crawler.models import DiscoveredJob

    url = HTMLParser(detail(3)).css_first('link[rel="canonical"]').attributes["href"]
    job = DiscoveredJob(
        source_name="vieclam24h",
        source_job_id="200945045",
        source_url=url,
        canonical_url=url,
        listing_url=START_URL,
    )
    r = record(detail(3), job)
    assert r.salary_raw is r.location_raw is r.posted_at_raw is None


def test_parser_detects_truncated_dom_and_id_conflict():
    html = detail(1)
    with pytest.raises(ValueError, match="full content mismatch"):
        record(html.replace("<p>Final duty.</p></div>", "</div>"))
    with pytest.raises(ValueError, match="embedded detail ID"):
        record(html.replace('"id":200941421', '"id":123456'))


def test_detail_title_whitespace_is_not_a_content_mismatch():
    html = detail(1)
    tree = HTMLParser(html)
    data = json.loads(tree.css_first("script#__NEXT_DATA__").text())
    original = data["props"]["initialState"]["api"]["jobDetailHiddenContact"]["data"]["title"]
    html = html.replace(json.dumps(original), json.dumps("  " + original.replace(" ", "  ") + "  "))
    assert record(html).job_title == original


@pytest.mark.parametrize(
    "changes",
    [
        {"max_details": 301},
        {"max_pages": 13},
        {"max_retries": 1},
        {"delay_min_seconds": 9},
        {"headed": False},
        {"fetcher": "http"},
        {"save_html": False},
        {"require_complete_content": False},
        {"mode": "sample"},
        {"authorization_reference": "NOT-SOURCE-PERMISSION"},
    ],
)
def test_bounded_config_rejects_unsafe_scope(tmp_path, changes):
    with pytest.raises(ConfigError):
        config(tmp_path, **changes).validate()


def test_cli_owner_browser_has_no_fake_source_reference(tmp_path):
    args = build_parser().parse_args(
        [
            "crawl",
            "vieclam24h",
            "--mode",
            "bounded",
            "--project-owner-public-test",
            "--fetcher",
            "playwright",
            "--headed",
            "--max-pages",
            "2",
            "--max-details",
            "20",
            "--delay-min",
            "10",
            "--delay-max",
            "15",
            "--max-retries",
            "0",
            "--save-html",
            "--require-complete-content",
        ]
    )
    c = _config_from_args(args)
    c.validate()
    assert c.authorization_reference is None and c.max_details == 20


class FakePage:
    def __init__(self, status, html):
        self.status, self.html = status, html
        self.url = "about:blank"
        self.calls = 0
        self.callbacks = []

    def on(self, event, callback):
        self.callbacks.append(callback)

    def goto(self, url, **kwargs):
        self.calls += 1
        self.url = url
        r = SimpleNamespace(
            url=url,
            status=self.status,
            headers={"content-type": "text/html"},
            body=lambda: self.html.encode(),
            request=SimpleNamespace(resource_type="document"),
        )
        for cb in self.callbacks:
            cb(r)
        return r

    def wait_for_timeout(self, ms):
        pass

    def content(self):
        return self.html

    def title(self):
        return "Page"

    def locator(self, selector):
        return SimpleNamespace(inner_text=lambda **kwargs: "Public content")

    def screenshot(self, *, path, full_page):
        Path(path).write_bytes(b"fixture PNG")

    def close(self):
        pass


@pytest.mark.parametrize(
    "status,html",
    [
        (401, "Denied"),
        (403, "Forbidden"),
        (429, "Slow down"),
        (200, "<title>Just a moment</title>cf-chl-test"),
        (200, '<html><body><div class="h-captcha"></div></body></html>'),
    ],
)
def test_browser_denial_saved_once_and_latched(tmp_path, monkeypatch, status, html):
    page = FakePage(status, html)
    f = Vieclam24hBrowserFetcher(config(tmp_path), sleep=lambda _: None)
    f.configure_run(tmp_path, "offline")
    f.robots_text = "User-agent: *\nAllow: /"
    context = SimpleNamespace(route=lambda *args: None, new_page=lambda: page)
    monkeypatch.setattr(f, "_ensure_started", lambda: setattr(f, "_context", context))
    with pytest.raises(FetchError) as caught:
        f.get(START_URL)
    assert caught.value.blocked
    with pytest.raises(FetchError, match="already stopped"):
        f.get(START_URL)
    assert page.calls == 1
    meta = json.loads(next((tmp_path / "http").glob("*.json")).read_text())
    assert meta["http_status"] == status and meta["blocked"]
    assert gzip.decompress((tmp_path / "http" / meta["body_path"]).read_bytes()).decode() == html


def test_robots_403_remains_unknown_not_a_listing_failure(tmp_path, monkeypatch):
    page = FakePage(403, "Forbidden")
    f = Vieclam24hBrowserFetcher(config(tmp_path), sleep=lambda _: None)
    f.configure_run(tmp_path, "offline")
    context = SimpleNamespace(route=lambda *args: None, new_page=lambda: page)
    monkeypatch.setattr(f, "_ensure_started", lambda: setattr(f, "_context", context))
    with pytest.raises(FetchError):
        f.get(ROBOTS)
    assert f.robots_text is None
    with pytest.raises(FetchError, match="already stopped"):
        f.get(START_URL)
    assert page.calls == 1


def test_browser_source_xhr_403_stops_even_main_document_200(tmp_path, monkeypatch):
    page = FakePage(200, "<html><body>Public page</body></html>")
    original = page.goto

    def goto(url, **kwargs):
        response = original(url, **kwargs)
        denied = SimpleNamespace(
            url="https://vieclam24h.vn/public-page-data",
            status=403,
            request=SimpleNamespace(resource_type="xhr"),
        )
        for callback in page.callbacks:
            callback(denied)
        return response

    monkeypatch.setattr(page, "goto", goto)
    f = Vieclam24hBrowserFetcher(config(tmp_path), sleep=lambda _: None)
    f.configure_run(tmp_path, "offline")
    f.robots_text = "User-agent: *\nAllow: /"
    monkeypatch.setattr(
        f,
        "_ensure_started",
        lambda: setattr(
            f, "_context", SimpleNamespace(route=lambda *args: None, new_page=lambda: page)
        ),
    )
    with pytest.raises(FetchError) as caught:
        f.get(START_URL)
    assert caught.value.blocked and caught.value.status_code == 200
    with pytest.raises(FetchError, match="already stopped"):
        f.get(START_URL)
    assert page.calls == 1
    meta = json.loads(next((tmp_path / "http").glob("*.json")).read_text())
    assert meta["source_denials"] == [
        {"url": "https://vieclam24h.vn/public-page-data", "status": 403}
    ]


def test_502_is_terminal_technical_error_not_access_denial(tmp_path, monkeypatch):
    page = FakePage(502, "<html><title>502 Bad Gateway</title><body>nginx</body></html>")
    f = Vieclam24hBrowserFetcher(config(tmp_path), sleep=lambda _: None)
    f.configure_run(tmp_path, "offline")
    f.robots_text = "User-agent: *\nAllow: /"
    monkeypatch.setattr(
        f,
        "_ensure_started",
        lambda: setattr(
            f, "_context", SimpleNamespace(route=lambda *args: None, new_page=lambda: page)
        ),
    )
    with pytest.raises(FetchError) as caught:
        f.get(START_URL)
    assert caught.value.terminal and not caught.value.blocked
    assert caught.value.status_code == 502 and not f.state.challenge_detected
    with pytest.raises(FetchError) as latched:
        f.get(START_URL)
    assert latched.value.terminal and not latched.value.blocked
    assert page.calls == 1
    meta = json.loads(next((tmp_path / "http").glob("*.json")).read_text())
    assert meta["http_status"] == 502 and not meta["blocked"]


def test_engine_terminal_502_does_not_issue_a_synthetic_next_detail(tmp_path):
    calls = []

    class MockFetcher:
        state = FetcherState(requested="playwright", active="playwright", headless=False)

        def configure_run(self, root, batch_id):
            pass

        def fallback(self, reason):
            return False

        def get(self, url):
            calls.append(url)
            bodies = {
                ROBOTS: "User-agent: *\nAllow: /",
                START_URL: (ROOT / "listing.html").read_text(),
            }
            if url not in bodies:
                raise FetchError(
                    "502 Bad Gateway", url=url, attempt=1, status_code=502, terminal=True
                )
            return FetchResponse(
                url=url,
                text=bodies[url],
                status_code=200,
                headers={},
                attempt=1,
                duration_seconds=0,
                fetcher="playwright",
            )

    manifest = CrawlEngine(config(tmp_path), Vieclam24hCrawler(), MockFetcher()).run()
    assert len(calls) == 3 and manifest.detail_requested == manifest.detail_failed == 1
    assert manifest.status == "stopped" and manifest.termination_reason == "detail_fetch_failed"
    assert not manifest.challenge_detected


@pytest.mark.parametrize(
    "status,body,blocked",
    [
        (200, "<html><main>Complete original HTTP content</main></html>", False),
        (403, "Forbidden", True),
        (200, '<html><div class="h-captcha"></div></html>', True),
    ],
)
def test_dom_and_artifact_failures_do_not_lose_original_http_response(
    tmp_path, monkeypatch, status, body, blocked
):
    page = FakePage(status, body)

    def fail_dom():
        raise PlaywrightError("Page is navigating and content is changing")

    def fail_artifact(*args, **kwargs):
        raise PlaywrightError("Secondary screenshot failure")

    monkeypatch.setattr(page, "content", fail_dom)
    monkeypatch.setattr(page, "close", fail_dom)
    f = Vieclam24hBrowserFetcher(config(tmp_path), sleep=lambda _: None)
    f.configure_run(tmp_path, "offline")
    f.robots_text = "User-agent: *\nAllow: /"
    monkeypatch.setattr(
        f,
        "_ensure_started",
        lambda: setattr(
            f, "_context", SimpleNamespace(route=lambda *args: None, new_page=lambda: page)
        ),
    )
    monkeypatch.setattr(f, "_save_artifacts", fail_artifact)
    with pytest.raises(FetchError) as caught:
        f.get(START_URL)
    assert caught.value.terminal and caught.value.status_code == status
    assert caught.value.blocked == blocked
    meta = json.loads(next((tmp_path / "http").glob("*.json")).read_text())
    assert meta["http_status"] == status and meta["html_path"] is None
    assert meta["original_error"] == "Page is navigating and content is changing"
    assert "Secondary screenshot failure" in meta["capture_errors"]
    assert gzip.decompress((tmp_path / "http" / meta["body_path"]).read_bytes()).decode() == body
    assert meta["body_sha256"] == hashlib.sha256(body.encode()).hexdigest()
    with pytest.raises(FetchError, match="already stopped"):
        f.get(START_URL)
    assert page.calls == 1


def test_goto_exception_preserves_observed_document_status_and_body(tmp_path, monkeypatch):
    page = FakePage(403, "Forbidden from observed response")
    original_goto = page.goto

    def fail_goto(url, **kwargs):
        original_goto(url, **kwargs)
        raise PlaywrightError("Original navigation failure")

    def fail_dom():
        raise PlaywrightError("Secondary DOM failure")

    monkeypatch.setattr(page, "goto", fail_goto)
    monkeypatch.setattr(page, "content", fail_dom)
    f = Vieclam24hBrowserFetcher(config(tmp_path), sleep=lambda _: None)
    f.configure_run(tmp_path, "offline")
    f.robots_text = "User-agent: *\nAllow: /"
    monkeypatch.setattr(
        f,
        "_ensure_started",
        lambda: setattr(
            f, "_context", SimpleNamespace(route=lambda *args: None, new_page=lambda: page)
        ),
    )
    with pytest.raises(FetchError) as caught:
        f.get(START_URL)
    assert caught.value.blocked and caught.value.status_code == 403
    meta = json.loads(next((tmp_path / "http").glob("*.json")).read_text())
    assert meta["original_error"] == "Original navigation failure"
    assert meta["http_status"] == 403
    assert (
        gzip.decompress((tmp_path / "http" / meta["body_path"]).read_bytes()).decode() == page.html
    )


def test_wildcard_robots_q_is_denied_before_navigation(tmp_path):
    f = Vieclam24hBrowserFetcher(config(tmp_path))
    f.configure_run(tmp_path, "offline")
    f.robots_text = "User-agent: *\nDisallow: /*?q"
    with pytest.raises(FetchError, match="scope/robots denied"):
        f.get(START_URL + "?q=engineer")


def test_engine_resume_dedup_and_public_page_two(tmp_path):
    first_html = (ROOT / "listing.html").read_text()
    second_html = first_html.replace('"current":1', '"current":2')
    second_html = second_html.replace("200941421", "200945045").replace(
        "fixture-one-c43p120", "fixture-three-c13p122"
    )
    urls = [
        HTMLParser(detail(i)).css_first('link[rel="canonical"]').attributes["href"]
        for i in (1, 2, 3)
    ]
    bodies = {
        ROBOTS: "User-agent: *\nAllow: /",
        START_URL: first_html,
        START_URL + "?page=2": second_html,
        **dict(zip(urls, [detail(i) for i in (1, 2, 3)], strict=True)),
    }
    calls = []

    class MockFetcher:
        state = FetcherState(requested="playwright", active="playwright", headless=False)

        def configure_run(self, *args):
            pass

        def fallback(self, reason):
            return False

        def get(self, url):
            calls.append(url)
            return FetchResponse(
                url=url,
                text=bodies[url],
                status_code=200,
                headers={},
                attempt=1,
                duration_seconds=0,
                fetcher="playwright",
            )

    c = config(tmp_path)
    first = CrawlEngine(c, Vieclam24hCrawler(), MockFetcher()).run()
    batch = next(tmp_path.glob("vieclam24h/snapshot_date=*/batch_id=*"))
    prefix = (batch / "jobs.jsonl").read_bytes()
    second = CrawlEngine(
        replace(c, resume=True, resume_batch_id=first.batch_id, max_pages=2, max_details=3),
        Vieclam24hCrawler(),
        MockFetcher(),
    ).run()
    raw = (batch / "jobs.jsonl").read_bytes()
    assert raw.startswith(prefix)
    assert second.records_written == second.detail_succeeded == second.detail_requested == 3
    assert second.cross_page_overlaps == 1
    assert all(calls.count(u) == 1 for u in urls)
    assert len({json.loads(line)["source_job_id"] for line in raw.splitlines()}) == 3


def test_offline_listing_recovery_idempotent_preserves_records_and_error(tmp_path):
    recover = runpy.run_path(
        str(Path(__file__).parents[2] / "scripts/recover_vieclam24h_listing.py")
    )["recover"]
    first_html = (ROOT / "listing.html").read_text()
    second_html = first_html.replace('"current":1', '"current":2')
    second_html = (
        second_html.replace("200941421", "200945045")
        .replace("fixture-one-c43p120", "fixture-three-c13p122")
        .replace("0201_1_", "0201_2_")
    )
    urls = [
        HTMLParser(detail(i)).css_first('link[rel="canonical"]').attributes["href"]
        for i in (1, 2, 3)
    ]
    bodies = {
        ROBOTS: "User-agent: *\nAllow: /",
        START_URL: first_html,
        START_URL + "?page=2": second_html,
        **dict(zip(urls, [detail(i) for i in (1, 2, 3)], strict=True)),
    }

    class MockFetcher:
        state = FetcherState(requested="playwright", active="playwright", headless=False)

        def configure_run(self, root, batch_id):
            self.root = root

        def fallback(self, reason):
            return False

        def get(self, url):
            if url.endswith("?page=2"):
                path = self.root / "http"
                path.mkdir(exist_ok=True)
                html = bodies[url].encode()
                (path / "page2.html.gz").write_bytes(gzip.compress(html))
                (path / "page2.json").write_text(
                    json.dumps(
                        {
                            "requested_url": url,
                            "final_url": url,
                            "http_status": 200,
                            "blocked": False,
                            "html_path": "page2.html.gz",
                            "html_sha256": hashlib.sha256(html).hexdigest(),
                            "requested_at": datetime.now(UTC).isoformat(),
                        }
                    )
                )
            return FetchResponse(
                url=url,
                text=bodies[url],
                status_code=200,
                headers={},
                attempt=1,
                duration_seconds=0,
                fetcher="playwright",
            )

    class OldPageOneSelector(Vieclam24hCrawler):
        def parse_listing(self, html, url):
            if url.endswith("?page=2"):
                raise ValueError("Old page-one-only tracking selector")
            return super().parse_listing(html, url)

    CrawlEngine(config(tmp_path, max_pages=2), OldPageOneSelector(), MockFetcher()).run()
    batch = next(tmp_path.glob("vieclam24h/snapshot_date=*/batch_id=*"))
    raw = (batch / "jobs.jsonl").read_bytes()
    error = (batch / "errors.jsonl").read_bytes()
    report = recover(batch, START_URL + "?page=2")
    assert report["new_requests"] == 0 and report["new_ids"] == 1 and report["overlaps"] == 1
    assert recover(batch, START_URL + "?page=2")["already_recovered"]
    assert (batch / "jobs.jsonl").read_bytes() == raw
    assert (batch / "errors.jsonl").read_bytes() == error
    manifest = json.loads((batch / "manifest.json").read_text())
    assert manifest["listing_pages_requested"] == manifest["listing_pages_succeeded"] == 2
    assert manifest["unique_ids_discovered"] == 3 and manifest["records_written"] == 2
    manifest["status"] = "stopped"
    manifest["challenge_detected"] = True
    (batch / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="access-blocked"):
        recover(batch, START_URL + "?page=2")


def test_offline_detail_recovery_writes_real_record_once_preserves_failure_evidence(tmp_path):
    recover = runpy.run_path(
        str(Path(__file__).parents[2] / "scripts/recover_vieclam24h_listing.py")
    )["recover_detail"]
    url = HTMLParser(detail(1)).css_first('link[rel="canonical"]').attributes["href"]
    bodies = {
        ROBOTS: "User-agent: *\nAllow: /",
        START_URL: (ROOT / "listing.html").read_text(),
        url: detail(1),
    }

    class MockFetcher:
        state = FetcherState(requested="playwright", active="playwright", headless=False)

        def configure_run(self, root, batch_id):
            self.root = root

        def fallback(self, reason):
            return False

        def get(self, target):
            if target == url:
                path = self.root / "http"
                path.mkdir(exist_ok=True)
                html = bodies[target].encode()
                (path / "detail.html.gz").write_bytes(gzip.compress(html))
                (path / "detail.json").write_text(
                    json.dumps(
                        {
                            "requested_url": target,
                            "final_url": target,
                            "http_status": 200,
                            "blocked": False,
                            "html_path": "detail.html.gz",
                            "html_sha256": hashlib.sha256(html).hexdigest(),
                            "requested_at": datetime.now(UTC).isoformat(),
                        }
                    )
                )
            return FetchResponse(
                url=target,
                text=bodies[target],
                status_code=200,
                headers={},
                attempt=1,
                duration_seconds=0,
                fetcher="playwright",
            )

    class OldStrictTitleParser(Vieclam24hCrawler):
        def parse_detail(self, *args, **kwargs):
            raise ValueError("Old whitespace-sensitive title comparison")

    before = CrawlEngine(config(tmp_path), OldStrictTitleParser(), MockFetcher()).run()
    assert before.detail_failed == 1 and before.records_written == 0
    batch = next(tmp_path.glob("vieclam24h/snapshot_date=*/batch_id=*"))
    errors = (batch / "errors.jsonl").read_bytes()
    html_path = batch / "html/200941421.html.gz"
    html_before = html_path.read_bytes()
    report = recover(batch, url)
    assert report["new_requests"] == 0 and report["appended_records"] == 1
    assert recover(batch, url)["already_recovered"]
    assert (batch / "errors.jsonl").read_bytes() == errors
    assert html_path.read_bytes() == html_before
    rows = [json.loads(line) for line in (batch / "jobs.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["source_job_id"] == "200941421"
    assert rows[0]["job_description"].endswith("Final duty.")
    manifest = json.loads((batch / "manifest.json").read_text())
    assert (
        manifest["detail_requested"]
        == manifest["detail_succeeded"]
        == manifest["records_written"]
        == 1
    )
    assert manifest["detail_failed"] == 0
