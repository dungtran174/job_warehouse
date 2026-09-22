from job_crawler.cli import main


def test_cli_refuses_live_access_without_authorization(monkeypatch, capsys) -> None:
    class NeverConstructFetcher:
        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("HTTP fetcher must not be constructed")

    monkeypatch.setattr("job_crawler.cli.create_fetcher", NeverConstructFetcher)
    result = main(["crawl", "topcv", "--user-agent", "crawler (contact=x@example.org)"])
    assert result == 2
    assert "authorization" in capsys.readouterr().err


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
