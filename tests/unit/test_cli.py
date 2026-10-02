from job_crawler.cli import _config_from_args, build_parser, main


def test_cli_refuses_live_access_without_declared_basis(monkeypatch, capsys) -> None:
    class NeverConstructFetcher:
        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("HTTP fetcher must not be constructed")

    monkeypatch.setattr("job_crawler.cli.create_fetcher", NeverConstructFetcher)
    result = main(["crawl", "topcv", "--user-agent", "crawler (contact=x@example.org)"])
    assert result == 2
    assert "access basis" in capsys.readouterr().err


def test_cli_refuses_full_snapshot_without_confirm_full(monkeypatch, capsys) -> None:
    class NeverConstructFetcher:
        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("HTTP fetcher must not be constructed")

    monkeypatch.setattr("job_crawler.cli.create_fetcher", NeverConstructFetcher)
    result = main(
        [
            "crawl",
            "topcv",
            "--mode",
            "full-snapshot",
            "--authorization-reference",
            "APPROVAL-TEST",
            "--user-agent",
            "crawler (contact=x@example.org)",
        ]
    )
    assert result == 2
    assert "confirm-full" in capsys.readouterr().err


def test_careerlink_target_command_parses_and_validates_offline() -> None:
    args = build_parser().parse_args(
        [
            "crawl",
            "careerlink",
            "--mode",
            "bounded",
            "--fetcher",
            "http",
            "--project-owner-public-test",
            "--max-pages",
            "8",
            "--max-details",
            "330",
            "--target-records",
            "300",
            "--delay-min",
            "10",
            "--delay-max",
            "15",
            "--max-retries",
            "0",
            "--require-complete-content",
            "--resume",
            "--resume-batch-id",
            "20260926T160422Z-c39d6a20",
            "--user-agent",
            "job-warehouse-crawler/0.1 (public academic research; single-threaded)",
        ]
    )
    config = _config_from_args(args)
    config.validate()
    assert config.target_records == 300 and config.max_details == 330
    assert config.resume and config.fetcher == "http"
    assert config.save_html is False
