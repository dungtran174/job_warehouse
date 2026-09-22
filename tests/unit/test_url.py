from job_crawler.utils.url import canonicalize_url, extract_topcv_job_id


def test_extract_job_id_and_reject_other_hosts() -> None:
    assert extract_topcv_job_id("https://www.topcv.vn/viec-lam/data-engineer/12345.html") == "12345"
    assert extract_topcv_job_id("https://example.com/viec-lam/data-engineer/12345.html") is None
    assert extract_topcv_job_id("https://www.topcv.vn/viec-lam/data-engineer.html") is None


def test_canonical_url_removes_tracking_and_keeps_functional_query() -> None:
    actual = canonicalize_url(
        "/viec-lam/data-engineer/123.html?utm_source=x&page=2&ref=home&u_sr_id=abc#top",
        "https://www.topcv.vn/jobs",
    )
    assert actual == "https://www.topcv.vn/viec-lam/data-engineer/123.html?page=2"
