import gzip
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
from job_crawler.crawlers.vietnamworks import VietnamWorksCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.base import FetchError, FetcherState, FetchResponse
from job_crawler.fetchers.factory import create_fetcher
from job_crawler.fetchers.vietnamworks_browser import ROBOTS, VietnamWorksBrowserFetcher
from job_crawler.models import DiscoveredJob

FIXTURE = Path(__file__).parents[1] / "fixtures/vietnamworks/rendered_detail_20260929.html"
URL = "https://www.vietnamworks.com/sample-2113254-jv"
START = "https://www.vietnamworks.com/viec-lam"


def config(tmp_path, **kw):
    values = dict(
        source="vietnamworks",
        mode="bounded",
        start_url=START,
        output_dir=tmp_path,
        project_owner_public_test=True,
        fetcher="playwright",
        headed=True,
        max_pages=2,
        max_details=20,
        save_html=True,
        require_complete_content=True,
        save_screenshot_on_error=True,
        delay_min_seconds=10,
        delay_max_seconds=15,
        max_retries=0,
    )
    values.update(kw)
    return CrawlConfig(**values)


@pytest.mark.parametrize(
    "kw",
    [
        {"max_details": 301},
        {"max_pages": 9},
        {"max_retries": 1},
        {"delay_min_seconds": 9},
        {"headed": False},
        {"save_html": False},
        {"require_complete_content": False},
        {"fetcher": "http"},
        {"authorization_reference": "NOT-A-SOURCE-APPROVAL"},
    ],
)
def test_bounded_browser_rejects_unsafe_scope(tmp_path, kw):
    with pytest.raises(ConfigError):
        config(tmp_path, **kw).validate()


def test_owner_browser_cli_and_factory(tmp_path):
    args = build_parser().parse_args(
        [
            "crawl",
            "vietnamworks",
            "--mode",
            "bounded",
            "--start-url",
            START,
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
    assert c.authorization_reference is None
    assert isinstance(create_fetcher(c), VietnamWorksBrowserFetcher)
    replace(config(tmp_path), mode="sample").validate()


def record(html):
    now = datetime.now(UTC)
    return VietnamWorksCrawler().parse_detail(
        html,
        DiscoveredJob(
            source_name="vietnamworks",
            source_job_id="2113254",
            source_url=URL,
            canonical_url=URL,
            listing_url=START,
        ),
        crawled_at=now,
        snapshot_date=now.date(),
        batch_id="offline",
        source_reported_total=None,
        raw_html_path=None,
    )


def test_full_rendered_detail_ignores_prompt_and_optional_missing_fields():
    r = record(FIXTURE.read_text())
    assert r.job_description == "First complete duty. Final complete duty."
    assert r.candidate_requirements == "First complete skill. Final complete skill."
    assert r.location_raw is None and r.company_size is None
    assert r.posted_at_raw == "2026-09-29T15:57:18+07:00"


@pytest.mark.parametrize("field", ["description", "requirements", "title", "company"])
def test_partial_or_wrong_rendered_detail_is_rejected(field):
    html = FIXTURE.read_text()
    if field == "description":
        html = html.replace("<p>Final complete duty.</p></div>", "</div>")
    elif field == "requirements":
        html = html.replace("<p>Final complete skill.</p></div>", "</div>")
    elif field == "title":
        html = html.replace("<h1>Sample quality job</h1>", "<h1>Wrong title</h1>")
    else:
        html = html.replace(">Sample employer</a>", ">Wrong employer</a>")
    with pytest.raises(ValueError, match="Rendered"):
        record(html)


class FakeLocator:
    first = property(lambda self: self)

    def wait_for(self, **kwargs):
        pass

    def inner_text(self, **kwargs):
        return "Public job content"


class FakePage:
    def __init__(self, status, html, *, dom_fails=False, xhr_denied=False, rendered_html=None):
        self.status, self.html = status, html
        self.dom_fails, self.xhr_denied = dom_fails, xhr_denied
        self.main_frame = object()
        self.url = "about:blank"
        self.callbacks = []
        self.calls = 0
        self.rendered_html = rendered_html
        self.section_waits = 0

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
            request=SimpleNamespace(resource_type="document", frame=self.main_frame, method="GET"),
        )
        for cb in self.callbacks:
            cb(r)
            if self.xhr_denied:
                cb(
                    SimpleNamespace(
                        url="https://ms.vietnamworks.com/job-search/v1.0/search",
                        status=403,
                        request=SimpleNamespace(resource_type="fetch", method="POST"),
                    )
                )
        return r

    def content(self):
        if self.dom_fails:
            raise PlaywrightError("Page is navigating during content capture")
        return self.html

    def title(self):
        node = HTMLParser(self.html).css_first("title")
        return node.text() if node else "Public page"

    def locator(self, selector):
        return FakeLocator()

    def wait_for_timeout(self, ms):
        pass

    def wait_for_function(self, expression, *, timeout):
        self.section_waits += 1
        assert "content.innerText.trim().length > 0" in expression
        assert timeout == 15000
        if self.rendered_html is not None:
            self.html = self.rendered_html
        tree = HTMLParser(self.html)
        sections = tree.css('div[class*="sc-1671001a-6"] > div')
        if len(sections) < 2 or not all(n.text(strip=True) for n in sections):
            raise PlaywrightError("Full detail sections did not render within timeout")

    def screenshot(self, *, path, full_page):
        Path(path).write_bytes(b"offline image fixture")

    def close(self):
        pass


def fetcher(tmp_path, monkeypatch, page):
    f = VietnamWorksBrowserFetcher(config(tmp_path), sleep=lambda _: None)
    f.configure_run(tmp_path, "offline")
    f.robots_text = "User-agent: *\nAllow: /"
    context = SimpleNamespace(route=lambda *args: None, new_page=lambda: page)
    monkeypatch.setattr(f, "_ensure_started", lambda: setattr(f, "_context", context))
    return f


@pytest.mark.parametrize(
    "status,html",
    [
        (401, "Denied"),
        (403, "Forbidden"),
        (429, "Slow down"),
        (200, '<title>Just a moment</title><div class="h-captcha"></div>'),
    ],
)
def test_blocked_response_saved_and_latched_without_second_navigation(
    tmp_path, monkeypatch, status, html
):
    page = FakePage(status, html)
    f = fetcher(tmp_path, monkeypatch, page)
    with pytest.raises(FetchError) as error:
        f.get(URL)
    assert error.value.blocked and error.value.terminal
    metadata = json.loads(next((tmp_path / "http").glob("*.json")).read_text())
    assert metadata["http_status"] == status and metadata["blocked"]
    with gzip.open(tmp_path / "http" / metadata["body_path"], "rt") as h:
        assert h.read() == html
    with pytest.raises(FetchError, match="already stopped"):
        f.get(URL)
    assert page.calls == 1


def test_original_http_survives_dom_error_and_no_next_get(tmp_path, monkeypatch):
    page = FakePage(200, FIXTURE.read_text(), dom_fails=True)
    f = fetcher(tmp_path, monkeypatch, page)
    with pytest.raises(FetchError) as error:
        f.get(URL)
    assert not error.value.blocked and error.value.terminal
    metadata = json.loads(next((tmp_path / "http").glob("*.json")).read_text())
    assert metadata["http_status"] == 200 and metadata["body_path"]
    assert "navigating" in metadata["original_error"]
    with pytest.raises(FetchError):
        f.get(URL)
    assert page.calls == 1


def test_http_200_with_source_json_403_stops_without_using_json(tmp_path, monkeypatch):
    page = FakePage(200, FIXTURE.read_text(), xhr_denied=True)
    f = fetcher(tmp_path, monkeypatch, page)
    with pytest.raises(FetchError) as error:
        f.get(URL)
    assert error.value.blocked
    metadata = json.loads(next((tmp_path / "http").glob("*.json")).read_text())
    assert metadata["http_status"] == 200 and metadata["source_denials"][0]["status"] == 403
    assert page.calls == 1


def loading_detail():
    tree = HTMLParser(FIXTURE.read_text())
    for section in tree.css('div[class*="sc-1671001a-6"]'):
        for child in list(section.iter()):
            child.decompose()
    return tree.html


def test_detail_waits_for_full_sections_without_retry_or_losing_http_body(tmp_path, monkeypatch):
    initial = loading_detail()
    with pytest.raises(ValueError, match="Rendered full"):
        record(initial)
    page = FakePage(200, initial, rendered_html=FIXTURE.read_text())
    response = fetcher(tmp_path, monkeypatch, page).get(URL)
    assert record(response.text).job_description.endswith("Final complete duty.")
    assert page.calls == page.section_waits == 1
    metadata = json.loads(next((tmp_path / "http").glob("*.json")).read_text())
    with gzip.open(tmp_path / "http" / metadata["body_path"], "rt") as h:
        assert h.read() == initial
    with gzip.open(tmp_path / "http" / metadata["html_path"], "rt") as h:
        assert h.read() == FIXTURE.read_text()


def test_unrendered_sections_stop_without_retry_and_keep_200_evidence(tmp_path, monkeypatch):
    page = FakePage(200, loading_detail())
    f = fetcher(tmp_path, monkeypatch, page)
    with pytest.raises(FetchError) as error:
        f.get(URL)
    assert error.value.terminal and not error.value.blocked
    metadata = json.loads(next((tmp_path / "http").glob("*.json")).read_text())
    assert metadata["http_status"] == 200 and not metadata["blocked"]
    assert "sections" in metadata["original_error"]
    with pytest.raises(FetchError, match="already stopped"):
        f.get(URL)
    assert page.calls == 1


def test_unknown_or_disallowed_robots_and_cross_host_fail_before_browser(tmp_path):
    f = VietnamWorksBrowserFetcher(config(tmp_path))
    f.configure_run(tmp_path, "offline")
    assert not f._allowed(START)
    f.robots_text = "User-agent: *\nDisallow: /viec-lam*"
    assert not f._allowed(START)
    assert not f._allowed("https://other.example/sample-2113254-jv")
    assert f._allowed(ROBOTS)


def test_offline_batch_audit_reads_real_storage_and_detects_truncation(tmp_path):
    listing = (
        '<div class="block-job-list"><div class="search_list">'
        f'<a href="{URL}">Sample</a></div></div>'
        '<ul class="pagination"><li class="active"><button>1</button></li></ul>'
    )

    class FixtureFetcher:
        state = FetcherState(requested="playwright", active="playwright", headless=False)

        def configure_run(self, root, batch_id):
            self.root = root
            (root / "http").mkdir()
            self.count = 0

        def get(self, url):
            self.count += 1
            text = (
                "User-agent: *\nAllow: /"
                if url == ROBOTS
                else (listing if url == START else FIXTURE.read_text())
            )
            name = f"{self.count}.html.gz"
            (self.root / "http" / name).write_bytes(gzip.compress(text.encode()))
            (self.root / "http" / f"{self.count}.json").write_text(
                json.dumps(
                    {
                        "requested_url": url,
                        "final_url": url,
                        "http_status": 200,
                        "html_path": name,
                        "blocked": False,
                        "source_denials": [],
                        "main_document_responses": [{"url": url, "status": 200}],
                    }
                )
            )
            return FetchResponse(
                url=url,
                text=text,
                status_code=200,
                headers={},
                attempt=1,
                duration_seconds=0,
                fetcher="playwright",
            )

        def fallback(self, reason):
            return False

    CrawlEngine(config(tmp_path), VietnamWorksCrawler(), FixtureFetcher()).run()
    root = next(tmp_path.glob("vietnamworks/snapshot_date=*/batch_id=*"))
    audit = runpy.run_path(str(Path(__file__).parents[2] / "scripts/audit_vietnamworks_batch.py"))[
        "audit"
    ]
    report = audit(root)
    assert report["records"] == report["main_listing_unique_ids"] == 1
    assert report["actual_detail_navigation_attempts"] == 1
    assert report["source_denial_count"] == report["duplicate_ids"] == 0
    assert report["full_description_and_requirements"] == 1
    row = json.loads((root / "jobs.jsonl").read_text())
    row["candidate_requirements"] = "First complete skill."
    (root / "jobs.jsonl").write_text(json.dumps(row) + "\n")
    with pytest.raises(AssertionError):
        audit(root)
