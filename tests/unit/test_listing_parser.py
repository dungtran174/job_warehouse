from job_crawler.parsers.topcv_listing import parse_listing


def test_listing_parser_handles_structured_data_featured_and_dedup(read_fixture) -> None:
    page = parse_listing(
        read_fixture("listing_page_1.html"),
        "https://www.topcv.vn/tim-viec-lam-moi-nhat?type_keyword=1&sba=1",
    )
    assert [job.source_job_id for job in page.jobs] == ["1001", "1002"]
    assert page.jobs[0].canonical_url == "https://www.topcv.vn/viec-lam/data-engineer/1001.html"
    assert page.source_reported_total == 1234
    assert page.next_url == "https://www.topcv.vn/tim-viec-lam-moi-nhat?page=2"


def test_listing_parser_accepts_schema_type_arrays() -> None:
    html = """
    <main>
      <script type="application/ld+json">
        {"@type": ["Thing", "ListItem"],
         "url": "https://www.topcv.vn/viec-lam/example/4321.html"}
      </script>
    </main>
    """
    page = parse_listing(html, "https://www.topcv.vn/jobs")
    assert [job.source_job_id for job in page.jobs] == ["4321"]


def test_empty_listing_has_stable_fingerprint(read_fixture) -> None:
    first = parse_listing(read_fixture("listing_empty.html"), "https://www.topcv.vn/jobs")
    second = parse_listing(read_fixture("listing_empty.html"), "https://www.topcv.vn/jobs?page=2")
    assert first.jobs == []
    assert first.fingerprint == second.fingerprint
