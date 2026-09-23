import pytest

from job_crawler.parsers.careerviet_listing import parse_listing

START_URL = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-vi.html"


def test_listing_extracts_stable_ids_deduplicates_and_finds_next_page(
    read_source_fixture,
) -> None:
    page = parse_listing(read_source_fixture("careerviet", "listing_page_1.html"), START_URL)

    assert [job.source_job_id for job in page.jobs] == ["35C00001", "35C00002"]
    assert all(job.source_name == "careerviet" for job in page.jobs)
    assert page.jobs[0].canonical_url == (
        "https://careerviet.vn/vi/tim-viec-lam/ky-su-du-lieu.35C00001.html"
    )
    assert page.source_reported_total == 1234
    assert page.next_url == ("https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-2-vi.html")


def test_listing_fingerprint_is_independent_of_duplicate_links(read_source_fixture) -> None:
    html = read_source_fixture("careerviet", "listing_page_1.html")
    first = parse_listing(html, START_URL)
    second = parse_listing(html.replace("Lặp", "Liên kết trùng"), START_URL)
    assert first.fingerprint == second.fingerprint


def test_second_and_last_pages_use_observed_canonical_navigation(read_source_fixture) -> None:
    second_url = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-2-vi.html"
    second = parse_listing(read_source_fixture("careerviet", "listing_page_2.html"), second_url)
    last = parse_listing(
        read_source_fixture("careerviet", "listing_last.html"),
        "https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-3-vi.html",
    )
    assert [job.source_job_id for job in second.jobs] == ["35C00003", "35C00004"]
    assert second.next_url == ("https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-3-vi.html")
    assert [job.source_job_id for job in last.jobs] == ["35C00005"]
    assert last.next_url is None


def test_different_listing_url_with_same_ids_has_same_fingerprint(read_source_fixture) -> None:
    html = read_source_fixture("careerviet", "listing_page_1.html")
    first = parse_listing(html, START_URL)
    repeated = parse_listing(
        html.replace(
            "https://careerviet.vn/viec-lam/tat-ca-viec-lam-vi.html",
            "https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-2-vi.html",
        ).replace(">1</a>", ">2</a>", 1),
        "https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-2-vi.html",
    )
    assert first.fingerprint == repeated.fingerprint


def test_same_id_with_different_job_url_is_rejected() -> None:
    html = (
        '<a class="job_link" href="/vi/tim-viec-lam/first.35C00001.html">First</a>'
        '<a class="job_link" href="/vi/tim-viec-lam/second.35C00001.html">Second</a>'
    )
    with pytest.raises(ValueError, match="Conflicting listing URLs"):
        parse_listing(html, START_URL)
