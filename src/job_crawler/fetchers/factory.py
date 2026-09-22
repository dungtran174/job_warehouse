from __future__ import annotations

from job_crawler.config import CrawlConfig
from job_crawler.fetchers.auto import AutoFetcher
from job_crawler.fetchers.base import Fetcher
from job_crawler.fetchers.http import HttpFetcher
from job_crawler.fetchers.playwright import PlaywrightFetcher


def create_fetcher(config: CrawlConfig) -> Fetcher:
    if config.fetcher == "http":
        return HttpFetcher(config)
    if config.fetcher == "playwright":
        return PlaywrightFetcher(config)
    return AutoFetcher(config)
