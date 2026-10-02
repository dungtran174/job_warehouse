from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from job_crawler.config import (
    DEFAULT_START_URLS,
    MEDIUM_MAX_DETAILS,
    MEDIUM_MAX_PAGES,
    PAGE6_CHECK_MAX_DETAILS,
    PAGE6_CHECK_MAX_PAGES,
    PILOT_MAX_DETAILS,
    PILOT_MAX_PAGES,
    SAMPLE_MAX_DETAILS,
    SAMPLE_MAX_PAGES,
    ConfigError,
    CrawlConfig,
)
from job_crawler.crawlers.base import SourceCrawler
from job_crawler.crawlers.careerlink import CareerLinkCrawler
from job_crawler.crawlers.careerviet import CareerVietCrawler
from job_crawler.crawlers.timviec365 import Timviec365Crawler
from job_crawler.crawlers.topcv import TopCVCrawler
from job_crawler.crawlers.vieclam24h import Vieclam24hCrawler
from job_crawler.crawlers.vietnamworks import VietnamWorksCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.factory import create_fetcher
from job_crawler.storage.jsonl import StorageError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-crawler")
    commands = parser.add_subparsers(dest="command", required=True)
    crawl = commands.add_parser("crawl", help="crawl one public job source")
    crawl.add_argument("source", choices=tuple(DEFAULT_START_URLS))
    crawl.add_argument(
        "--mode",
        choices=("sample", "medium", "pilot", "page6-check", "bounded", "full-snapshot"),
        default="sample",
    )
    crawl.add_argument("--start-url")
    crawl.add_argument("--output-dir", type=Path)
    crawl.add_argument("--max-pages", type=int, help="cumulative listing attempts in this batch")
    crawl.add_argument(
        "--max-details", type=int, help="cumulative detail attempts, not raw records"
    )
    crawl.add_argument(
        "--target-records",
        type=int,
        help="CareerLink bounded: stop at this total of unique raw records (at most 300)",
    )
    crawl.add_argument("--timeout", type=float)
    crawl.add_argument("--delay-min", type=float)
    crawl.add_argument("--delay-max", type=float)
    crawl.add_argument("--max-retries", type=int)
    crawl.add_argument("--user-agent")
    crawl.add_argument("--log-level")
    crawl.add_argument("--fetcher", choices=("auto", "http", "playwright"))
    crawl.add_argument("--headed", action="store_true")
    crawl.add_argument(
        "--save-html",
        action="store_true",
        help="save parsed HTML; CareerLink without this keeps only metadata for successful bodies",
    )
    crawl.add_argument("--save-screenshot-on-error", action="store_true")
    crawl.add_argument(
        "--require-complete-content",
        action="store_true",
        help="stop if company, description, or candidate requirements are missing",
    )
    crawl.add_argument("--resume", action="store_true")
    crawl.add_argument(
        "--resume-batch-id",
        help="resume this exact batch ID instead of selecting the latest resumable batch",
    )
    crawl.add_argument("--confirm-full", action="store_true")
    crawl.add_argument(
        "--authorization-reference",
        help="non-secret reference to genuine written authorization from the source",
    )
    crawl.add_argument(
        "--project-owner-public-test",
        action="store_true",
        help="owner-directed public sample (VietnamWorks/CareerLink: 2 listings/20 details; "
        "bounded mode: CareerLink 8 listings/330 attempts, at most 300 target records; "
        "Timviec365 13/300, "
        "Việc Làm 24h 12/300, VietnamWorks 8/300 (ordinary browser); "
        "other sources: 1 listing/3 details); "
        "not source authorization",
    )
    return parser


def _config_from_args(args: argparse.Namespace) -> CrawlConfig:
    max_pages = args.max_pages
    max_details = args.max_details
    if args.mode == "sample":
        default_pages = 1 if args.project_owner_public_test else SAMPLE_MAX_PAGES
        default_details = 3 if args.project_owner_public_test else SAMPLE_MAX_DETAILS
        max_pages = default_pages if max_pages is None else max_pages
        max_details = default_details if max_details is None else max_details
    elif args.mode == "medium":
        max_pages = MEDIUM_MAX_PAGES if max_pages is None else max_pages
        max_details = MEDIUM_MAX_DETAILS if max_details is None else max_details
    elif args.mode == "pilot":
        max_pages = PILOT_MAX_PAGES if max_pages is None else max_pages
        max_details = PILOT_MAX_DETAILS if max_details is None else max_details
    elif args.mode == "page6-check":
        max_pages = PAGE6_CHECK_MAX_PAGES if max_pages is None else max_pages
        max_details = PAGE6_CHECK_MAX_DETAILS if max_details is None else max_details
    overrides: dict[str, object] = {
        "source": args.source,
        "mode": args.mode,
        "start_url": args.start_url or DEFAULT_START_URLS[args.source],
        "max_pages": max_pages,
        "max_details": max_details,
        "target_records": args.target_records,
        "save_html": args.save_html,
        "headed": args.headed,
        "save_screenshot_on_error": args.save_screenshot_on_error,
        "require_complete_content": args.require_complete_content,
        "resume": args.resume,
        "resume_batch_id": args.resume_batch_id,
        "confirm_full": args.confirm_full,
        "authorization_reference": args.authorization_reference,
        "project_owner_public_test": args.project_owner_public_test,
    }
    for argument, field in (
        (args.output_dir, "output_dir"),
        (args.timeout, "timeout_seconds"),
        (args.delay_min, "delay_min_seconds"),
        (args.delay_max, "delay_max_seconds"),
        (args.max_retries, "max_retries"),
        (args.user_agent, "user_agent"),
        (args.log_level, "log_level"),
        (args.fetcher, "fetcher"),
    ):
        if argument is not None:
            overrides[field] = argument
    return CrawlConfig.from_environment(**overrides)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = _config_from_args(args)
        config.validate()
    except (ConfigError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    crawlers: dict[str, SourceCrawler] = {
        "topcv": TopCVCrawler(),
        "careerviet": CareerVietCrawler(),
        "careerlink": CareerLinkCrawler(),
        "timviec365": Timviec365Crawler(),
        "vieclam24h": Vieclam24hCrawler(),
        "vietnamworks": VietnamWorksCrawler(),
    }
    crawler = crawlers[config.source]
    try:
        with create_fetcher(config) as fetcher:
            manifest = CrawlEngine(config, crawler, fetcher).run()
    except StorageError as exc:
        print(f"Storage error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if manifest.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
