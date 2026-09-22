from job_crawler.utils.hash import job_content_hash, stable_hash


def test_stable_hash_ignores_dictionary_order_and_whitespace() -> None:
    assert stable_hash({"b": "x  y", "a": 1}) == stable_hash({"a": 1, "b": "x y"})


def test_job_hash_ignores_crawl_metadata_but_changes_with_content() -> None:
    base = {"job_title": "Data Engineer", "company_name": "Example", "crawled_at": "one"}
    changed_metadata = {**base, "crawled_at": "two"}
    changed_content = {**base, "job_title": "Senior Data Engineer"}
    assert job_content_hash(base) == job_content_hash(changed_metadata)
    assert job_content_hash(base) != job_content_hash(changed_content)
