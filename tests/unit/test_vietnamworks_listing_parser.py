from pathlib import Path
from urllib.parse import urljoin

import pytest
from selectolax.parser import HTMLParser

from job_crawler.parsers.vietnamworks_detail import job_id_from_url
from job_crawler.parsers.vietnamworks_listing import parse_listing

ROOT = Path(__file__).parents[1] / "fixtures/vietnamworks"
START = "https://www.vietnamworks.com/tim-viec-lam/tim-tat-ca-viec-lam"


def test_primary_pages_and_observed_pagination():
    first = parse_listing((ROOT / "main_listing_1.html").read_text(), START)
    second = parse_listing((ROOT / "main_listing_2.html").read_text(), first.next_url)
    assert len(first.jobs) == len(second.jobs) == 50
    ids1 = {j.source_job_id for j in first.jobs}
    ids2 = {j.source_job_id for j in second.jobs}
    assert not ids1 & ids2
    assert "999999" not in ids1 | ids2
    assert first.next_url == "https://www.vietnamworks.com/viec-lam?page=2"
    assert second.next_url == "https://www.vietnamworks.com/viec-lam?page=3"
    assert all("?" not in j.canonical_url for j in first.jobs)
    assert first.fingerprint != second.fingerprint


def test_featured_only_is_not_a_main_listing():
    page = parse_listing((ROOT / "listing_jd_excerpt.html").read_text(), START)
    assert page.jobs == []
    assert page.next_url is None


def test_unverified_pagination_fails_closed():
    with pytest.raises(ValueError, match="active pagination"):
        parse_listing((ROOT / "main_listing_1.html").read_text(), START + "?page=2")


def test_discovery_landing_ids_and_carousel_are_not_main_results():
    url = "https://www.vietnamworks.com/tim-viec-lam"
    html = (ROOT / "discovery_landing_20260929.html").read_text()
    tree = HTMLParser(html)
    ids = {
        job_id_from_url(urljoin(url, anchor.attributes["href"]))
        for anchor in tree.css('[data-cname="preview-job"] a[href]')
    }
    assert ids == {"2099338", "2113189"}
    assert len(tree.css('[data-id^="recommend-jobs-pagination-"]')) == 2
    assert "Loading" not in html
    page = parse_listing(html, url)
    assert page.jobs == []
    assert page.next_url is None
    # A landing total is neither a main listing count nor detail discovery.
    assert page.source_reported_total is None
