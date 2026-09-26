import gzip
import runpy
from datetime import UTC, datetime
from pathlib import Path

from selectolax.parser import HTMLParser

from job_crawler.models import DiscoveredJob
from job_crawler.parsers.careerlink import parse_detail

AUDIT = runpy.run_path(str(Path(__file__).parents[2] / "scripts/audit_careerlink_batch.py"))[
    "audit"
]


def test_audit_detects_content_loss_and_duplicate_id(tmp_path):
    html = (Path(__file__).parents[1] / "fixtures/careerlink/detail_1.html").read_text()
    url = HTMLParser(html).css_first('link[rel="canonical"]').attributes["href"]
    now = datetime.now(UTC)
    job = DiscoveredJob(
        source_name="careerlink",
        source_job_id="3634108",
        source_url=url,
        canonical_url=url,
        listing_url="https://www.careerlink.vn/vieclam/list",
    )
    record = parse_detail(
        html,
        job,
        crawled_at=now,
        snapshot_date=now.date(),
        batch_id="offline",
        source_reported_total=None,
        raw_html_path="detail.html.gz",
    )
    (tmp_path / "detail.html.gz").write_bytes(gzip.compress(html.encode()))
    (tmp_path / "jobs.jsonl").write_text(record.model_dump_json() + "\n")
    assert AUDIT(tmp_path)["errors"] == []
    record.job_description = "truncated"
    (tmp_path / "jobs.jsonl").write_text((record.model_dump_json() + "\n") * 2)
    errors = AUDIT(tmp_path)["errors"]
    assert "DOM mismatch: 3634108/job_description" in errors
    assert "Duplicate ID: 3634108" in errors
    assert "Hash mismatch: 3634108" in errors
