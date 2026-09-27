import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import respx
from selectolax.parser import HTMLParser

from job_crawler.config import ConfigError, CrawlConfig
from job_crawler.crawlers.timviec365 import Timviec365Crawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.timviec365 import ROBOTS, Timviec365HttpFetcher
from job_crawler.parsers.timviec365 import START
from job_crawler.storage.jsonl import StorageError


def config(tmp_path):
    return CrawlConfig(
        source="timviec365",
        start_url=START,
        output_dir=tmp_path,
        project_owner_public_test=True,
        user_agent="offline-test",
        max_pages=1,
        max_details=3,
        fetcher="http",
        save_html=True,
        require_complete_content=True,
        delay_min_seconds=10,
        delay_max_seconds=15,
        max_retries=0,
    )


def setup_routes():
    fixture = Path(__file__).parents[1] / "fixtures/timviec365/detail_2070499.html"
    raw = fixture.read_text()
    ids = [str(2070499 + i) for i in range(6)]
    urls = []
    details = []
    for job_id in ids:
        html = raw.replace("2070499", job_id)
        url = HTMLParser(html).css_first('link[rel="canonical"]').attributes["href"]
        urls.append(url)
        details.append(respx.get(url).mock(return_value=httpx.Response(200, text=html)))

    def listing(indices, next_page):
        cards = "".join(
            f'<div class="item_vl" data-newid="{ids[i]}" data-newghim="0">'
            f'<h2 class="box_title_new"><a class="title_new" href="{urls[i]}">Job</a>'
            "</h2></div>"
            for i in indices
        )
        html = (
            '<div class="boxContentListNew"><div class="boxShowListNew">' + cards + "</div></div>"
        )
        if next_page:
            html += (
                '<ul class="pagination"><li class="pagi_pre">'
                f'<a href="/viec-lam?page={next_page}">&gt;</a></li></ul>'
            )
        return html

    respx.get(ROBOTS).mock(return_value=httpx.Response(200, text="User-agent: *\nAllow: /"))
    page1 = respx.get(url__regex=r"https://timviec365\.vn/viec-lam$").mock(
        return_value=httpx.Response(200, text=listing(range(3), 2))
    )
    page2 = respx.get(START + "?page=2").mock(
        return_value=httpx.Response(200, text=listing([2, 3, 4, 5], None))
    )
    return page1, page2, details


def run(c):
    with Timviec365HttpFetcher(c, sleep=lambda _: None) as fetcher:
        return CrawlEngine(c, Timviec365Crawler(), fetcher).run()


@respx.mock
def test_sample_to_bounded_page2_then_detail_milestones_preserve_prefix(tmp_path):
    page1, page2, details = setup_routes()
    c = config(tmp_path)
    first = run(c)
    root = next(tmp_path.glob("timviec365/snapshot_date=*/batch_id=*"))
    before = (root / "jobs.jsonl").read_bytes()
    c = replace(c, mode="bounded", max_pages=2, resume=True, resume_batch_id=first.batch_id)
    discovery = run(c)  # max_details remains 3: test page 2 without new details.
    assert discovery.mode == "bounded" and discovery.records_written == 3
    assert discovery.unique_ids_discovered == 6
    assert discovery.new_job_ids_per_page == [3, 3] and discovery.cross_page_overlaps == 1
    assert (root / "jobs.jsonl").read_bytes() == before
    for cap in (4, 6, 6):
        last = run(replace(c, max_details=cap))
        assert last.records_written == last.detail_requested == last.detail_succeeded == cap
    assert page1.call_count == page2.call_count == 1
    assert all(r.call_count == 1 for r in details)
    payload = (root / "jobs.jsonl").read_bytes()
    assert payload.startswith(before)
    assert len({json.loads(line)["source_job_id"] for line in payload.splitlines()}) == 6
    assert last.access_basis == "project_owner_public_test" and last.authorization_reference is None
    with pytest.raises(StorageError, match="mode"):
        run(replace(c, mode="sample", max_pages=1))


@respx.mock
def test_transition_requires_completed_three_detail_sample_and_explicit_batch(tmp_path):
    setup_routes()
    c = config(tmp_path)
    first = run(replace(c, max_details=1))
    bounded = replace(c, mode="bounded", resume=True, resume_batch_id=first.batch_id)
    with pytest.raises(StorageError, match="mode"):
        run(bounded)


@pytest.mark.parametrize("pages,details", [(2, 30), (5, 100), (13, 300)])
def test_bounded_explicit_milestone_caps(tmp_path, pages, details):
    replace(config(tmp_path), mode="bounded", max_pages=pages, max_details=details).validate()


@pytest.mark.parametrize(
    "change",
    [
        {"max_pages": 14},
        {"max_pages": None},
        {"max_details": 301},
        {"max_details": None},
        {"max_pages": 0},
        {"max_details": 0},
        {"project_owner_public_test": False},
        {"fetcher": "auto"},
        {"max_retries": 1},
        {"delay_min_seconds": 9},
        {"save_html": False},
        {"require_complete_content": False},
    ],
)
def test_bounded_guards_remain_strict(tmp_path, change):
    with pytest.raises(ConfigError):
        replace(config(tmp_path), mode="bounded", **change).validate()


@respx.mock
def test_page2_offline_recovery_preserves_records_and_is_idempotent(tmp_path, monkeypatch):
    from job_crawler.parsers.timviec365 import parse_listing
    from job_crawler.storage.timviec365_recovery import recover_page2

    setup_routes()
    fixture = Path(__file__).parents[1] / "fixtures/timviec365/page2_arrows.html"
    page2_html = fixture.read_text()
    respx.get(START + "?page=2").mock(return_value=httpx.Response(200, text=page2_html))
    c = config(tmp_path)
    first = run(c)
    root = next(tmp_path.glob("timviec365/snapshot_date=*/batch_id=*"))
    original = (root / "jobs.jsonl").read_bytes()
    original_parser = Timviec365Crawler.parse_listing

    def old_listing_parser(self, html, listing_url):
        if listing_url.endswith("?page=2"):
            raise ValueError("Non-sequential Timviec365 pagination")
        return original_parser(self, html, listing_url)

    with monkeypatch.context() as patch:
        patch.setattr(Timviec365Crawler, "parse_listing", old_listing_parser)
        result = run(
            replace(c, mode="bounded", max_pages=2, resume=True, resume_batch_id=first.batch_id)
        )
    assert result.pagination_termination_reason == "listing_parse_failed"
    page = parse_listing(page2_html, START + "?page=2")
    assert page.next_url == START + "?page=3"
    meta_path = next(
        p
        for p in (root / "http").glob("*.json")
        if json.loads(p.read_text())["requested_url"].endswith("?page=2")
    )
    requests_before = len(respx.calls)
    assert recover_page2(root, meta_path) == 1
    assert recover_page2(root, meta_path) == 0
    assert len(respx.calls) == requests_before
    assert (root / "jobs.jsonl").read_bytes() == original
    recovered = json.loads((root / "manifest.json").read_text())
    assert recovered["listing_pages_requested"] == recovered["listing_pages_succeeded"] == 2
    assert recovered["unique_ids_discovered"] == 4
    assert len((root / "errors.jsonl").read_text().splitlines()) == 1
    metadata = json.loads(meta_path.read_text())
    metadata["challenge_detected"] = True
    meta_path.write_text(json.dumps(metadata))
    with pytest.raises(StorageError, match="verified"):
        recover_page2(root, meta_path)


@respx.mock
def test_offline_audit_detects_cut_text_and_duplicate_ids(tmp_path):
    import subprocess
    import sys

    from job_crawler.utils.hash import job_content_hash

    setup_routes()
    run(config(tmp_path))
    root = next(tmp_path.glob("timviec365/snapshot_date=*/batch_id=*"))
    script = Path(__file__).parents[2] / "scripts/audit_timviec365_batch.py"
    command = [sys.executable, str(script), str(root), "--output", str(tmp_path / "audit.json")]
    subprocess.run(command, check=True, capture_output=True, text=True)
    result = json.loads((tmp_path / "audit.json").read_text())
    assert (
        result["records"]
        == result["source_total_unique_ids"]
        == result["whole_html_sections_verified"]
        == 3
    )
    original = (root / "jobs.jsonl").read_text()
    rows = [json.loads(line) for line in original.splitlines()]
    rows[0]["job_description"] = rows[0]["job_description"][:8]
    rows[0]["content_hash"] = job_content_hash(rows[0])
    (root / "jobs.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    truncated = subprocess.run(command, capture_output=True, text=True)
    assert truncated.returncode != 0 and "Truncated/different" in truncated.stderr
    (root / "jobs.jsonl").write_text(original + original.splitlines()[0] + "\n")
    duplicate = subprocess.run(command, capture_output=True, text=True)
    assert duplicate.returncode != 0 and "Duplicate ID" in duplicate.stderr


@respx.mock
def test_interrupted_attempt_stays_counted_and_completed_details_are_not_refetched(tmp_path):
    from job_crawler.storage.jsonl import BatchStorage

    page1, page2, details = setup_routes()
    c = config(tmp_path)
    first = run(c)
    c = replace(c, mode="bounded", max_pages=2, resume=True, resume_batch_id=first.batch_id)
    run(c)  # Discover the second page without fetching new details.
    root = next(tmp_path.glob("timviec365/snapshot_date=*/batch_id=*"))
    original = (root / "jobs.jsonl").read_bytes()
    storage = BatchStorage.resume(root)
    interrupted = storage.checkpoint.next_detail()
    assert interrupted is not None
    manifest = storage.read_manifest()
    manifest.detail_requested += 1  # Interruption before a response was saved.
    manifest.status = "running"
    storage.write_manifest(manifest)
    storage.close()

    last = run(replace(c, max_details=6))
    assert last.detail_requested == 6
    assert last.records_written == last.detail_succeeded == 5
    assert last.detail_failed == 0 and not last.challenge_detected
    assert last.termination_reason == "max_details"
    assert (root / "jobs.jsonl").read_bytes().startswith(original)
    assert page1.call_count == page2.call_count == 1
    assert [route.call_count for route in details] == [1, 1, 1, 1, 1, 0]
